import os
import sys
import subprocess
from tabulate import tabulate
from colorama import Fore, Style, init

# Initialize colorama
init(autoreset=True)

# Variables
ANSIBLE_CONTAINER_NAME = "ansible-container"
WORKER_CONTAINER_PREFIX = "worker-container"
WORKER_COUNT = 5
STATIC_IPS = ["172.18.0.3", "172.18.0.5", "172.18.0.7", "172.18.0.9", "172.18.0.11"]
NETWORK_NAME = "ansible_network"
DOCKER_HUB = "sandeep1415/devops"
MASTER = "ansible-controller"
HOST = "ansible-hosts"

# Function to run shell commands and capture output
def run_command(command, timeout=120):
    """Run a shell command and return the result with a timeout"""
    try:
        result = subprocess.run(command, shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, timeout=timeout)
        if result.returncode != 0:
            print(f"{Fore.RED}Error: {result.stderr.strip()}{Style.RESET_ALL}")
        return result
    except subprocess.TimeoutExpired:
        print(f"{Fore.RED}Error: The command timed out!{Style.RESET_ALL}")
        return None
    except KeyboardInterrupt:
        print(f"\n{Fore.YELLOW}Process interrupted! Exiting...{Style.RESET_ALL}")
        sys.exit(1)

# Function to check if a Docker image exists locally
def docker_image_exists(image_name):
    """Check if a Docker image exists locally"""
    result = run_command(f"docker images -q {image_name}")
    return bool(result.stdout.strip())

# Function to pull Docker images if not present
def ensure_docker_image(image_name):
    """Ensure Docker image is present, pulling if necessary"""
    if docker_image_exists(image_name):
        print(f"{Fore.YELLOW}Image already exists: {image_name}{Style.RESET_ALL}")
    else:
        pull_docker_image(image_name)

# Function to pull Docker images with progress display
def pull_docker_image(image_name):
    """Pull Docker image with progress display"""
    print(f"{Fore.CYAN}Pulling Docker image '{image_name}'...{Style.RESET_ALL}")
    
    # Run the docker pull command and stream the output to show progress
    result = subprocess.Popen(f"docker pull {image_name}", shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)

    # Display the output line by line, so we can track the progress
    for line in result.stdout:
        # Print each line of the pull progress
        sys.stdout.write(f"{Fore.GREEN}{line.strip()}{Style.RESET_ALL}\n")  # Append new lines instead of overwriting
        sys.stdout.flush()

    # Wait for the result to finish
    result.wait()

    if result.returncode == 0:
        print(f"{Fore.GREEN}Image pulled successfully: {image_name}{Style.RESET_ALL}")
    else:
        print(f"{Fore.RED}Failed to pull image: {image_name}{Style.RESET_ALL}")
        sys.exit(1)

# Function to check if a network exists
def check_network():
    result = subprocess.run(f"docker network inspect {NETWORK_NAME}", shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    return result.returncode == 0

# Function to ensure network exists
def ensure_network():
    if check_network():
        return f"{Fore.YELLOW}Exists{Style.RESET_ALL}"
    else:
        print(f"{Fore.YELLOW}Network '{NETWORK_NAME}' not found. Creating...{Style.RESET_ALL}")
        result = run_command(f"docker network create --subnet=172.18.0.0/16 {NETWORK_NAME}")
        if result and result.returncode == 0:
            return f"{Fore.GREEN}Created{Style.RESET_ALL}"
        else:
            print(f"{Fore.RED}Failed to create network: {result.stderr.strip() if result else 'Unknown Error'}{Style.RESET_ALL}")
            sys.exit(1)

# Function to check if a container exists
def check_container(container_name):
    result = run_command(f"docker ps -aq -f name={container_name}")
    return bool(result.stdout.strip())

# Progress bar function with smooth updates
def progress_bar(current, total):
    percent = int((current / total) * 100)
    bar = '=' * (percent // 5)
    sys.stdout.write(f'\r|{bar:<20}| {percent}%')
    sys.stdout.flush()

# Function to display the table
def display_table(headers, table):
    print(tabulate(table, headers, tablefmt="grid"))

# Start Containers
def start_containers():
    total_steps = 1 + WORKER_COUNT  # 1 step for Ansible container, WORKER_COUNT steps for worker containers
    current_step = 0

    all_containers_table = []

    # Ensure network exists
    network_status = ensure_network()
    all_containers_table.append([f"{Fore.CYAN}Network '{NETWORK_NAME}': {network_status}{Style.RESET_ALL}"])

    # Pull the required Docker images
    print("Checking Docker images...")
    ensure_docker_image(f"{DOCKER_HUB}:{MASTER}")  # Ensure the ansible-controller image is present
    ensure_docker_image(f"{DOCKER_HUB}:{HOST}")  # Ensure the ansible-hosts image is present
    print("Docker images checked.")

    # Start Ansible container
    if check_container(ANSIBLE_CONTAINER_NAME):
        ansible_status = f"{Fore.YELLOW}Exists{Style.RESET_ALL}"
    else:
        result = run_command(f"docker run -d --name {ANSIBLE_CONTAINER_NAME} --network {NETWORK_NAME} {DOCKER_HUB}:{MASTER} bash -c 'tail -f /dev/null'")
        if result and result.returncode == 0:
            ansible_status = f"{Fore.GREEN}Started{Style.RESET_ALL}"
        else:
            ansible_status = f"{Fore.RED}Failed: {result.stderr.strip() if result else 'Unknown Error'}{Style.RESET_ALL}"
    current_step += 1
    progress_bar(current_step, total_steps)
    all_containers_table.append([f"{Fore.CYAN}{ANSIBLE_CONTAINER_NAME}: {ansible_status}{Style.RESET_ALL}"])

    # Start worker containers
    for i in range(1, WORKER_COUNT + 1):
        WORKER_CONTAINER_NAME = f"{WORKER_CONTAINER_PREFIX}{i}"
        if check_container(WORKER_CONTAINER_NAME):
            worker_status = f"{Fore.YELLOW}Exists{Style.RESET_ALL}"
        else:
            IP_ADDRESS = STATIC_IPS[i - 1]
            result = run_command(f"docker run -d --name {WORKER_CONTAINER_NAME} --network {NETWORK_NAME} --ip {IP_ADDRESS} {DOCKER_HUB}:{HOST} bash -c 'apt update && apt install -y openssh-server && service ssh start && tail -f /dev/null'")
            if result and result.returncode == 0:
                worker_status = f"{Fore.GREEN}Started{Style.RESET_ALL}"
            else:
                worker_status = f"{Fore.RED}Failed: {result.stderr.strip() if result else 'Unknown Error'}{Style.RESET_ALL}"
        current_step += 1
        progress_bar(current_step, total_steps)
        all_containers_table.append([f"{Fore.CYAN}{WORKER_CONTAINER_NAME}: {worker_status}{Style.RESET_ALL}"])

    print("\n")
    display_table(["Container Status"], all_containers_table)
    print("Ansible setup complete!")

# Stop Containers
def stop_containers():
    containers = run_command("docker ps -aq").stdout.splitlines()
    total_steps = len(containers) * 2  # Each container has two steps (stop and remove)
    current_step = 0

    stop_remove_table = []
    headers = ["Operation", "Progress"]
    for container in containers:
        # Stopping container
        run_command(f"docker stop {container}")
        current_step += 1
        progress_bar(current_step, total_steps)
        stop_remove_table.append([f"{Fore.CYAN}Stopping {container}{Style.RESET_ALL}", f"{Fore.GREEN}Stopped{Style.RESET_ALL}"])

    for container in containers:
        # Removing container
        run_command(f"docker rm -f {container}")
        current_step += 1
        progress_bar(current_step, total_steps)
        stop_remove_table.append([f"{Fore.CYAN}Removing {container}{Style.RESET_ALL}", f"{Fore.GREEN}Removed{Style.RESET_ALL}"])

    print("\n")
    display_table(headers, stop_remove_table)
    print("All containers stopped and removed.")

    print("Pruning unused Docker networks...")
    run_command("docker network prune -f")
    print("Unused Docker networks pruned.")

    print("Environment cleanup complete. Docker images are retained.")

# Ping Ansible to all worker containers
def ping_ansible():
    print("Pinging all worker containers from Ansible...")
    result = run_command(f"docker exec {ANSIBLE_CONTAINER_NAME} ansible all -m ping -e 'ansible_ssh_common_args=\"-o StrictHostKeyChecking=no\"'")
    if result and result.returncode == 0:
        ping_results = result.stdout.splitlines()
        for line in ping_results:
            if '"ping": "pong"' in line:
                print(f"{Fore.GREEN}{line}{Style.RESET_ALL}")
            else:
                print(f"{Fore.YELLOW}{line}{Style.RESET_ALL}")
    else:
        error_message = f"{Fore.RED}Failed to ping: {result.stderr.strip() if result else 'Unknown Error'}{Style.RESET_ALL}"
        print(error_message)

# Handle command-line arguments
if __name__ == "__main__":
    if len(sys.argv) == 1 or sys.argv[1] == "start":
        start_containers()
    elif sys.argv[1] == "stop":
        stop_containers()
    elif sys.argv[1] == "ping":
        ping_ansible()
    else:
        error_message = f"{Fore.RED}Invalid argument! Use 'start', 'stop', or 'ping'.{Style.RESET_ALL}"
        print(error_message)
        sys.exit(1)


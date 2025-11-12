#!/usr/bin/env python3
"""
Sync whitelist_config.py from Docker volume to project directory
This script can be run manually or as a shutdown hook
"""
import os
import sys
import subprocess
from pathlib import Path

def find_container():
    """Find the Docker container name"""
    try:
        # Try docker-compose naming
        result = subprocess.run(
            ["docker", "ps", "-a", "--format", "{{.Names}}"],
            capture_output=True,
            text=True,
            timeout=5
        )
        containers = result.stdout.strip().split('\n')
        
        # Look for bot container
        for container in containers:
            if 'telegram' in container.lower() or 'bot' in container.lower() or 'adick' in container.lower():
                return container
        
        return None
    except Exception as e:
        print(f"Error finding container: {e}")
        return None

def sync_config_from_container(container_name, source_path, dest_path):
    """Copy config file from Docker container to project directory"""
    try:
        # Check if source exists in container
        check_cmd = ["docker", "exec", container_name, "test", "-f", source_path]
        result = subprocess.run(check_cmd, capture_output=True, timeout=5)
        
        if result.returncode != 0:
            print(f"⚠️  Config file not found in container: {source_path}")
            return False
        
        # Copy file from container
        copy_cmd = ["docker", "cp", f"{container_name}:{source_path}", dest_path]
        result = subprocess.run(copy_cmd, capture_output=True, text=True, timeout=10)
        
        if result.returncode == 0:
            print(f"✅ Successfully synced whitelist_config.py")
            print(f"📝 Destination: {Path(dest_path).absolute()}")
            return True
        else:
            print(f"❌ Failed to copy: {result.stderr}")
            return False
            
    except subprocess.TimeoutExpired:
        print("❌ Operation timed out")
        return False
    except Exception as e:
        print(f"❌ Error: {e}")
        return False

def sync_from_volume(volume_name, dest_path):
    """Try to extract config from Docker volume"""
    try:
        # Create temporary container to access volume
        temp_container = f"temp_sync_{os.getpid()}"
        
        # Run temporary container with volume
        run_cmd = [
            "docker", "run", "--rm",
            "--name", temp_container,
            "-v", f"{volume_name}:/data",
            "alpine:latest",
            "cat", "/data/whitelist_config.py"
        ]
        
        result = subprocess.run(run_cmd, capture_output=True, text=True, timeout=10)
        
        if result.returncode == 0 and result.stdout:
            # Write to destination
            with open(dest_path, 'w', encoding='utf-8') as f:
                f.write(result.stdout)
            print(f"✅ Successfully synced from volume: {volume_name}")
            return True
        else:
            print(f"⚠️  Could not read from volume")
            return False
            
    except Exception as e:
        print(f"❌ Error accessing volume: {e}")
        return False

def main():
    """Main sync function"""
    print("🔄 Syncing whitelist_config.py from Docker...")
    
    # Paths
    source_path = "/app/config/whitelist_config.py"
    dest_path = Path(__file__).parent.parent / "whitelist_config.py"
    
    # Try to find container
    container = find_container()
    
    if container:
        print(f"📦 Found container: {container}")
        if sync_config_from_container(container, source_path, str(dest_path)):
            return 0
    
    # Try volume approach
    print("📦 Trying to access Docker volume...")
    volume_name = "adick_bot_whitelist_config"
    if sync_from_volume(volume_name, str(dest_path)):
        return 0
    
    print("⚠️  Could not sync config. It may not have been modified in Docker.")
    return 1

if __name__ == "__main__":
    sys.exit(main())


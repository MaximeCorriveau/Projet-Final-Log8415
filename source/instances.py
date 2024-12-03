import boto3
import os
from scripts import worker_script, manager_script, gatekeeper_script, trust_host_script, proxy_script
import time
import requests

class EC2Manager:
    def __init__(self):
        self.ec2 = boto3.resource('ec2', region_name='us-east-1')
        self.ec2_client = boto3.client('ec2', region_name='us-east-1')
        self.instances_worker = []
        self.instances_manager = []
        self.key_pair_name = 'my_key_pair'
        self.userData_worker = worker_script
        self.userData_manager = manager_script
        self.userData_gatekeeper = gatekeeper_script
        self.userData_trust_host = trust_host_script
        self.userData_proxy = proxy_script

    def create_key_pair(self):
        try:
            key_pair = self.ec2_client.create_key_pair(KeyName=self.key_pair_name)
            private_key = key_pair['KeyMaterial']
            key_pair_file = f"{self.key_pair_name}.pem"

            with open(key_pair_file, "w") as file:
                file.write(private_key)

            print(f"Key pair '{self.key_pair_name}' created and saved as '{key_pair_file}'")
        except self.ec2_client.exceptions.ClientError as e:
            if 'InvalidKeyPair.Duplicate' in str(e):
                print(f"Key pair '{self.key_pair_name}' already exists.")
            else:
                raise
    
    def delete_key_pair(self):
        try:
            self.ec2_client.delete_key_pair(KeyName=self.key_pair_name)
            print(f"Deleted key pair '{self.key_pair_name}' from AWS.")

            key_pair_file = f"{self.key_pair_name}.pem"
            if os.path.exists(key_pair_file):
                os.remove(key_pair_file)
                print(f"Deleted local key pair file '{key_pair_file}'.")
        except self.ec2_client.exceptions.ClientError as e:
            print(f"Error deleting key pair: {e}")

    def wait_for_instances(self, instances):
        for instance in instances:
            instance.wait_until_running()
            instance.reload()

    def launch_instances(self, security_group_id, security_group_id_gatekeeper):
        # Lancer des instances t2.micro renommées worker
        self.instances_worker = self.ec2.create_instances(
            ImageId='ami-0e86e20dae9224db8',
            MinCount=2,
            MaxCount=2,
            InstanceType='t2.micro',
            SecurityGroupIds=[security_group_id],
            KeyName=self.key_pair_name,
            UserData=self.userData_worker
        )
        self.wait_for_instances(self.instances_worker)
        self.worker_instances = self.instances_worker
        worker_ips = [instance.private_ip_address for instance in self.worker_instances]
        worker_public_ips = [instance.public_ip_address for instance in self.worker_instances]
        print(f"Worker IPs: {worker_public_ips}")

        self.userData_manager = self.userData_manager.replace("worker1_ip", worker_public_ips[0]).replace("worker2_ip", worker_public_ips[1])
        self.instances_manager = self.ec2.create_instances(
            ImageId='ami-0e86e20dae9224db8',
            MinCount=1,
            MaxCount=1,
            InstanceType='t2.micro',
            SecurityGroupIds=[security_group_id],
            KeyName=self.key_pair_name,
            UserData=self.userData_manager
        )
        self.wait_for_instances(self.instances_manager)
        self.manager_instance = self.instances_manager[0]
        self.manager_ip = self.manager_instance.private_ip_address
        self.manager_public_ip = self.manager_instance.public_ip_address
        print(f"Manager IP: {self.manager_public_ip}")
        # Lancer une instance t2.large

        self.userData_proxy = self.userData_proxy.replace("manager_ip", self.manager_public_ip)
        self.userData_proxy = self.userData_proxy.replace("worker1_ip", worker_public_ips[0]).replace("worker2_ip", worker_public_ips[1])
        self.instances_proxy = self.ec2.create_instances(
            ImageId='ami-0e86e20dae9224db8',
            MinCount=1,
            MaxCount=1,
            InstanceType='t2.large',
            SecurityGroupIds=[security_group_id],
            KeyName=self.key_pair_name,
            UserData=self.userData_proxy
        )
        self.wait_for_instances(self.instances_proxy)
        self.proxy_instance = self.instances_proxy[0]
        self.proxy_ip = self.proxy_instance.private_ip_address
        self.proxy_public_ip = self.proxy_instance.public_ip_address

        self.userData_trust_host = self.userData_trust_host.replace("proxy_ip", self.proxy_public_ip)
        print(f"Proxy IP: {self.proxy_public_ip}")
        self.instances_trust_host = self.ec2.create_instances(
            ImageId='ami-0e86e20dae9224db8',
            MinCount=1,
            MaxCount=1,
            InstanceType='t2.large',
            SecurityGroupIds=[security_group_id],
            KeyName=self.key_pair_name,
            UserData=self.userData_trust_host
        )
        self.wait_for_instances(self.instances_trust_host)
        self.trust_host_instance = self.instances_trust_host[0]
        self.trust_host_ip = self.trust_host_instance.private_ip_address
        self.trust_host_public_ip = self.trust_host_instance.public_ip_address
        print(f"Trust Host IP: {self.trust_host_public_ip}")
        self.userData_gatekeeper = self.userData_gatekeeper.replace("trust_host_ip", self.trust_host_public_ip)
        self.instances_gatekeeper = self.ec2.create_instances(
            ImageId='ami-0e86e20dae9224db8',
            MinCount=1,
            MaxCount=1,
            InstanceType='t2.large',
            SecurityGroupIds=[security_group_id_gatekeeper],
            KeyName=self.key_pair_name,
            UserData=self.userData_gatekeeper
        )
        self.wait_for_instances(self.instances_gatekeeper)
        self.gatekeeper_instance = self.instances_gatekeeper[0]

    def create_security_group(self, vpc_id):
        response = self.ec2.create_security_group(
            GroupName='my-security-group',
            Description='Security group for ALB and EC2 instances',
            VpcId=vpc_id
        )
        security_group_id = response.group_id

        self.ec2_client.authorize_security_group_ingress(
            GroupId=security_group_id,
            IpPermissions=[
                {
                    'IpProtocol': 'tcp',
                    'FromPort': 8000,
                    'ToPort': 8000,
                    'IpRanges': [{'CidrIp': '0.0.0.0/0'}]
                },
                {
                    'IpProtocol': 'tcp',
                    'FromPort': 22,
                    'ToPort': 22,
                    'IpRanges': [{'CidrIp': "0.0.0.0/0"}]
                }
            ]
        )

        print(f"Created Security Group: {security_group_id}")
        return security_group_id

    def create_gatekeeper_security_group(self, vpc_id):
        # Créer un groupe de sécurité pour le service Gatekeeper
        response = self.ec2.create_security_group(
            GroupName='gatekeeper-security-group',
            Description='Security group for Gatekeeper service',
            VpcId=vpc_id
        )
        security_group_id = response.group_id
        print(f"Created Security Group: {security_group_id}")

        # Autoriser le trafic sur le port 5000 pour le Gatekeeper
        self.ec2_client.authorize_security_group_ingress(
            GroupId=security_group_id,
            IpPermissions=[
                {
                    'IpProtocol': 'tcp',
                    'FromPort': 5000,
                    'ToPort': 5000,
                    'IpRanges': [{'CidrIp': '0.0.0.0/0'}]  # Modifier selon les besoins de sécurité
                },
                {
                    'IpProtocol': 'tcp',
                    'FromPort': 22,
                    'ToPort': 22,
                    'IpRanges': [{'CidrIp': '0.0.0.0/0'}]  # À restreindre en production
                }
            ]
        )

        return security_group_id

    def cleanup_resources(self):
        input(f"\nReady to terminate EC2 instances. Press Enter to proceed...")

        # Terminer les instances EC2
        instances = self.ec2_client.describe_instances()
        instance_ids = [
            instance['InstanceId']
            for reservation in instances['Reservations']
            for instance in reservation['Instances']
            if instance['State']['Name'] != 'terminated'
        ]

        if instance_ids:
            self.ec2_client.terminate_instances(InstanceIds=instance_ids)
            self.ec2_client.get_waiter('instance_terminated').wait(InstanceIds=instance_ids)
            print(f"Terminated instances: {instance_ids}")

        # Supprimer le groupe de sécurité 'my-security-group'
        response = self.ec2_client.describe_security_groups(
            Filters=[{'Name': 'group-name', 'Values': ['my-security-group']}]
        )

        if response['SecurityGroups']:
            security_group = response['SecurityGroups'][0]
            security_group_id = security_group['GroupId']

            try:
                self.ec2_client.delete_security_group(GroupId=security_group_id)
                print(f"Deleted Security Group: my-security-group")
            except self.ec2_client.exceptions.ClientError as e:
                print(f"Error deleting security group: {e}")

        # Supprimer le groupe de sécurité 'gatekeeper'
        response = self.ec2_client.describe_security_groups(
            Filters=[{'Name': 'group-name', 'Values': ['gatekeeper-security-group']}]
        )

        if response['SecurityGroups']:
            security_group = response['SecurityGroups'][0]
            security_group_id = security_group['GroupId']

            try:
                self.ec2_client.delete_security_group(GroupId=security_group_id)
                print(f"Deleted Security Group: gatekeeper-security-group")
            except self.ec2_client.exceptions.ClientError as e:
                print(f"Error deleting security group: {e}")

        # Supprimer la paire de clés
        self.delete_key_pair()


    
    def benchmark(self):
        gatekeeper_ip = self.gatekeeper_instance.public_ip_address
        print(f"Gatekeeper IP: {gatekeeper_ip}")
        gatekeeper_url = f"http://{gatekeeper_ip}:5000"  # Gatekeeper runs on port 5000
        modes = ["direct_hit", "random", "customized"]
        queries = {
            "read": "SELECT * FROM actor LIMIT 10;",
            "write": "INSERT INTO actor (first_name, last_name) VALUES ('Benchmark', 'Test');"
        }

        results = {}
        input(f"\nPress Enter to start the benchmark test...")
        for mode in modes:
            print(f"\n=== Testing mode: {mode} ===")
            mode_results = {"read_times": [], "write_times": []}
            errors = {"read_errors": [], "write_errors": []}

            for query_type, query in queries.items():
                num_requests = 2  # Adjust as needed
                times = []
                print(f"  {query_type.capitalize()} Queries:")

                for i in range(num_requests):
                    start_time = time.time()
                    # Payload in the updated format
                    payload = {
                        "action": query_type,   # Specifies "read" or "write"
                        "query": query,        # The actual query
                        "mode": mode           # Execution mode (direct_hit, random, etc.)
                    }
                    try:
                        response = requests.post(gatekeeper_url, json=payload)
                        elapsed_time = time.time() - start_time

                        if response.status_code == 200:
                            times.append(elapsed_time)
                            print(f"    Response: {response.json()}")
                            print(f"    Request {i+1}: Success (Time: {elapsed_time:.4f} seconds)")
                        else:
                            error_message = f"Error {response.status_code}: {response.text}"
                            errors[f"{query_type}_errors"].append(error_message)
                            print(f"    Request {i+1}: Failed - {error_message}")
                    except requests.exceptions.RequestException as e:
                        error_message = f"Request exception: {str(e)}"
                        errors[f"{query_type}_errors"].append(error_message)
                        print(f"    Request {i+1}: Failed - {error_message}")

                average_time = sum(times) / len(times) if times else float('inf')
                mode_results[f"{query_type}_average_time"] = average_time
                print(f"  Average {query_type} time for mode {mode}: {average_time:.4f} seconds")

            results[mode] = mode_results
            results[mode].update(errors)  # Add errors to results

        print("\n=== Benchmark results summary ===")
        for mode, stats in results.items():
            print(f"Mode: {mode}")
            print(f"  Average Read Time: {stats.get('read_average_time', float('inf')):.4f} seconds")
            print(f"  Average Write Time: {stats.get('write_average_time', float('inf')):.4f} seconds")
            if stats.get("read_errors"):
                print(f"  Read Errors: {stats['read_errors']}")
            if stats.get("write_errors"):
                print(f"  Write Errors: {stats['write_errors']}")

        return results

def main():
    ec2_manager = EC2Manager()
    ec2_manager.create_key_pair()
    vpc_id = ec2_manager.ec2_client.describe_vpcs()["Vpcs"][0]['VpcId']
    security_group = ec2_manager.create_security_group(vpc_id)
    security_group_gatekeeper = ec2_manager.create_gatekeeper_security_group(vpc_id)
    ec2_manager.launch_instances(security_group, security_group_gatekeeper)
    ec2_manager.benchmark()
    ec2_manager.cleanup_resources()

if __name__ == "__main__":
    main()

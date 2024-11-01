import boto3, json
import sys, os, time
from botocore.exceptions import ClientError
import paramiko

def get_key_pair(ec2_client):
    """
        Retrieve the key pair
        Args:
            ec2_client: The boto3 ec2 client
        Returns:
            Key name
        """
    key_name = "key_final"
    try:
        ec2_client.describe_key_pairs(KeyNames=[key_name])
        print(f"Key Pair {key_name} already exists. Using the existing key.")
        return key_name

    except ClientError as e:
        if 'InvalidKeyPair.NotFound' in str(e):
            try:
                # Create a key pair if it doesnt exist
                response = ec2_client.create_key_pair(KeyName=key_name)
                private_key = response['KeyMaterial']

                # Save the key to directory
                save_directory = os.path.expanduser('~/.aws')
                key_file_path = os.path.join(save_directory, f"{key_name}.pem")

                with open(key_file_path, 'w') as file:
                    file.write(private_key)

                os.chmod(key_file_path, 0o400)
                print(f"Created and using Key Pair: {key_name}")
                return key_name
            except ClientError as e:
                print(f"Error creating key pair: {e}")
                sys.exit(1)
        else:
            print(f"Error retrieving key pairs: {e}")
            sys.exit(1)

def get_vpc_id(ec2_client):
    """
        Function to get VPC id
        Args:
            ec2_client: The boto3 ec2 client
        Returns:
            VPC id
        """
    try:
        # Get all VPC's
        response = ec2_client.describe_vpcs()
        vpcs = response.get('Vpcs', [])
        if not vpcs:
            print("Error: No VPCs found.")
            sys.exit(1)
        print(f"Using VPC ID: {vpcs[0]['VpcId']}")
        # Take the first one
        return vpcs[0]['VpcId']

    except ClientError as e:
        print(f"Error retrieving VPCs: {e}")
        sys.exit(1)

def create_security_group(ec2_client, vpc_id, group_name):
    """
    Create or reuse a security group with valid inbound rules.
    Args:
        ec2_client: The boto3 ec2 client.
        vpc_id: VPC id.
    Returns:
        Security group id.
    """
    inbound_rules_public = [
        {'protocol': 'tcp', 'port_range': 5000, 'source': '0.0.0.0/0'},
        {'protocol': 'tcp', 'port_range': 5001, 'source': '0.0.0.0/0'},
        {'protocol': 'tcp', 'port_range': 22, 'source': '0.0.0.0/0'},
    ]
    inbound_rules_private = [
        {'protocol': 'tcp', 'port_range': 3306, 'source': '0.0.0.0/0'},  # Allow MySQL traffic only within the VPC
        {'protocol': 'tcp', 'port_range': 5000, 'source': '0.0.0.0/0'},  # Allow proxy-to-manager or worker traffic only within the VPC
        {'protocol': 'tcp', 'port_range': 22, 'source': '0.0.0.0/0'}
    ]

    try:
        # Check if the security group already exists
        response = ec2_client.describe_security_groups(
            Filters=[
                {'Name': 'group-name', 'Values': [group_name]},
                {'Name': 'vpc-id', 'Values': [vpc_id]}
            ]
        )
        if response['SecurityGroups']:
            security_group_id = response['SecurityGroups'][0]['GroupId']
            print(f"Using existing Security Group ID: {security_group_id}")
            return security_group_id

        # If the security group doesn't exist, create a new one
        print(f"Creating security group {group_name} in VPC ID: {vpc_id}")
        response = ec2_client.create_security_group(
            GroupName=group_name,
            Description="x",
            VpcId=vpc_id
        )
        security_group_id = response['GroupId']
        print(f"Created Security Group ID: {security_group_id}")

        #set inbound rules
        inbound_rules = inbound_rules_public if group_name == "public" else inbound_rules_private
        ip_permissions = []
        for rule in inbound_rules:
            ip_permissions.append({
                'IpProtocol': 'tcp',
                'FromPort': rule['port_range'],
                'ToPort': rule['port_range'],
                'IpRanges': [{'CidrIp': rule['source']}]
            })

        # Add inbound rules
        ec2_client.authorize_security_group_ingress(
            GroupId=security_group_id,
            IpPermissions=ip_permissions
        )

        return security_group_id

    except ClientError as e:
        if 'InvalidPermission.Duplicate' in str(e):
            print(f"Ingress rule already exists for Security Group: {group_name}")
        else:
            print(f"Error adding ingress rules: {e}")
        return None

def get_subnet(ec2_client, vpc_id):
    """
    Function to get 2 Subnet ID
    Args:
        ec2_client: The boto3 ec2 client
        vpc_id: VPC id
    Returns:
        Subnet ID
    """
    try:
        response = ec2_client.describe_subnets(
            Filters=[
                {
                    'Name': 'vpc-id',
                    'Values': [vpc_id]
                }
            ]
        )
        subnets = response.get('Subnets', [])
        if not subnets:
            print("Error: No subnets found in the VPC.")
            sys.exit(1)

        print(f"Using Subnet public ID: {subnets[1]['SubnetId']} and private ID: {subnets[0]['SubnetId']}")
        return subnets[1]['SubnetId'], subnets[0]['SubnetId']
    except ClientError as e:
        print(f"Error retrieving subnets: {e}")
        sys.exit(1)

def create_internet_gateway(ec2_client, vpc_id):
    # Create and attach an Internet Gateway
    igw = ec2_client.create_internet_gateway()
    igw_id = igw['InternetGateway']['InternetGatewayId']
    print('test')
    # Attach the internet gateway to the specified VPC
    ec2_client.attach_internet_gateway(InternetGatewayId=igw_id, VpcId=vpc_id)
    print(f"Created and attached Internet Gateway: {igw_id} to VPC: {vpc_id}")
    return igw

def create_route(ec2_client, vpc_id, subnet_id, igw_id):
    # Create a route table for the specified VPC
    route_table = ec2_client.create_route_table(VpcId=vpc_id)
    route_table_id = route_table['RouteTable']['RouteTableId']

    # Create a route that directs all traffic (0.0.0.0/0) through the Internet Gateway
    ec2_client.create_route(
        RouteTableId=route_table_id,
        DestinationCidrBlock='0.0.0.0/0',
        GatewayId=igw_id
    )

    # Associate the route table with the specified subnet
    ec2_client.associate_route_table(RouteTableId=route_table_id, SubnetId=subnet_id)

    print(f"Created route for subnet: {subnet_id} via IGW: {igw_id}")

def launch_bastion(ec2_client, image_id, instance_type, key_name, security_group_id, subnet_id):
    try:
        response = ec2_client.run_instances(
            ImageId=image_id,
            MinCount=1,
            MaxCount=1,
            InstanceType=instance_type,
            KeyName=key_name,
            SecurityGroupIds=[security_group_id],
            SubnetId=subnet_id,
            #UserData=user_data_script,
            TagSpecifications=[
                {
                    'ResourceType': 'instance',
                    'Tags': [
                        {
                            'Key': 'Name',
                            'Value': 'LabInstance'
                        }
                    ]
                }
            ]
        )

        ec2_resource = boto3.resource('ec2')

        # Retrieve instance objects using the InstanceId
        bastion_list = [ec2_resource.Instance(instance['InstanceId']) for instance in response['Instances']]
        bastion = bastion_list[0]

        bastion.wait_until_running()
        bastion.reload()

        print(f"Bastion launched IP: {bastion.public_ip_address}   ID: {bastion.id}")

        return bastion

    except ClientError as e:
        print(f"Error launching instances: {e}")
        sys.exit(1)

def launch_workers(ec2_client, image_id, instance_type, key_name, security_group_id,
                   subnet_id, num_of_instance, manager_ip, log_file, log_pos):
    """
    Launches EC2 worker instance.
    Args:
        ec2_client: The EC2 client.
        image_id: The AMI ID for the instance.
        instance_type: The type of instance (e.g., 't2.micro').
        key_name: The key pair name to use for SSH access.
        security_group_id: The security group ID.
        subnet_id: The subnet ID.
    Returns:
        orchestrator instance
    """
    user_data_script = f'''#!/bin/bash
                            sudo apt update -y
                            sudo apt install mysql-server -y
                            
                            sudo apt install -y python3-pip python3-venv
                            cd /home/ubuntu
                            python3 -m venv venv
                            echo "source venv/bin/activate" >> /home/ubuntu/.bashrc
                            source venv/bin/activate
                            
                            pip3 install flask requests redis
                            sudo chown -R ubuntu:ubuntu /home/ubuntu/venv
                            pip install mysql-connector-python
                            
                            sudo sed -i '/server-id/d' /etc/mysql/mysql.conf.d/mysqld.cnf
                            echo "server-id={num_of_instance + 2}" | sudo tee -a /etc/mysql/mysql.conf.d/mysqld.cnf
                            sudo sed -i "s/bind-address\s*=.*/bind-address = 0.0.0.0/" /etc/mysql/mysql.conf.d/mysqld.cnf
                            sudo systemctl restart mysql
                            sudo mysql -e "
                            CREATE USER 'replica'@'%' IDENTIFIED WITH mysql_native_password BY 'replica_password';
                            GRANT SELECT ON sakila.* TO 'replica'@'%';
                            FLUSH PRIVILEGES;

                            CHANGE MASTER TO
                                MASTER_HOST = '{manager_ip}', 
                                MASTER_USER = 'replica', 
                                MASTER_PASSWORD = 'replica_password', 
                                MASTER_LOG_FILE = '{log_file}', 
                                MASTER_LOG_POS = {log_pos};
                            START SLAVE;
                            "
                            
                            # Wait for the worker_manager_app.py file to be transferred
                            while [ ! -f /home/ubuntu/worker_manager_app.py ]; do
                                sleep 5
                            done

                            python3 worker_manager_app.py
                            '''

    try:
        response = ec2_client.run_instances(
            ImageId=image_id,
            MinCount=1,
            MaxCount=1,
            InstanceType=instance_type,
            KeyName=key_name,
            SecurityGroupIds=[security_group_id],
            SubnetId=subnet_id,
            UserData=user_data_script,
            TagSpecifications=[
                {
                    'ResourceType': 'instance',
                    'Tags': [
                        {
                            'Key': 'Name',
                            'Value': 'LabInstance'
                        }
                    ]
                }
            ]
        )

        ec2_resource = boto3.resource('ec2')

        instance_objects = [ec2_resource.Instance(instance['InstanceId']) for instance in response['Instances']]
        worker = instance_objects[0]

        # Wait for all instances to be in "running" state and collect instance details
        for instance in instance_objects:
            instance.wait_until_running()
            instance.reload()  # Reload instance attributes to get updated info
            print(f"Worker instance IP: {instance.public_ip_address}   ID: {instance.id}")

        return worker

    except ClientError as e:
        print(f"Error launching instances: {e}")
        sys.exit(1)


def launch_manager(ec2_client, image_id, instance_type, key_name, security_group_id, subnet_id):
    """
    Launches EC2 orchestrator instance.
    Args:
        ec2_client: The EC2 client.
        image_id: The AMI ID for the instance.
        instance_type: The type of instance (e.g., 't2.micro').
        key_name: The key pair name to use for SSH access.
        security_group_id: The security group ID.
        subnet_id: The subnet ID.
    Returns:
        orchestrator instance
    """
    user_data_script = '''#!/bin/bash 
                                # Update and install MySQL
                                sudo apt update -y
                                sudo apt install mysql-server -y

                                # Configure MySQL as a replication source
                                sudo sed -i '/\[mysqld\]/a server-id=1\nlog_bin=/var/log/mysql/mysql-bin.log' /etc/mysql/mysql.conf.d/mysqld.cnf
                            sudo sed -i "s/bind-address\s*=.*/bind-address = 0.0.0.0/" /etc/mysql/mysql.conf.d/mysqld.cnf

                                # Restart MySQL to apply changes
                                sudo systemctl restart mysql

                                # Set up MySQL replication user
                                sudo mysql -e "
                                CREATE USER 'replica'@'%' IDENTIFIED WITH mysql_native_password BY 'replica_password';
                                CREATE USER 'replica'@'localhost' IDENTIFIED WITH mysql_native_password BY 'replica_password';
                                GRANT REPLICATION SLAVE ON *.* TO 'replica'@'%';
                                GRANT ALL PRIVILEGES ON sakila.* TO 'replica'@'%';
                                GRANT ALL PRIVILEGES ON sakila.* TO 'replica'@'localhost';
                                FLUSH PRIVILEGES;
                                "
                                
                                # Save the replication status log file and position for workers
                                sudo mysql -e "SHOW MASTER STATUS\G" | tee /home/ubuntu/master_status.txt
                                
                                sleep 180

                                # Download and install the Sakila database
                                wget https://downloads.mysql.com/docs/sakila-db.tar.gz
                                tar -xzf sakila-db.tar.gz
                                sudo mysql < sakila-db/sakila-schema.sql
                                sudo mysql < sakila-db/sakila-data.sql
                                
                                sudo apt install -y python3-pip python3-venv
                                cd /home/ubuntu
                                python3 -m venv venv
                                echo "source venv/bin/activate" >> /home/ubuntu/.bashrc
                                source venv/bin/activate
                                
                                pip3 install flask requests redis
                                sudo chown -R ubuntu:ubuntu /home/ubuntu/venv
                                pip install mysql-connector-python
                                
                                # Wait for the worker_manager_app.py file to be transferred
                            while [ ! -f /home/ubuntu/worker_manager_app.py ]; do
                                sleep 5
                            done
                            python3 -m venv venv
                            echo "source venv/bin/activate" >> /home/ubuntu/.bashrc
                            source venv/bin/activate
                            python3 worker_manager_app.py
                                '''

    try:
        response = ec2_client.run_instances(
            ImageId=image_id,
            MinCount=1,
            MaxCount=1,
            InstanceType=instance_type,
            KeyName=key_name,
            SecurityGroupIds=[security_group_id],
            SubnetId=subnet_id,
            UserData=user_data_script,
            TagSpecifications=[
                {
                    'ResourceType': 'instance',
                    'Tags': [
                        {
                            'Key': 'Name',
                            'Value': 'LabInstance'
                        }
                    ]
                }
            ]
        )

        ec2_resource = boto3.resource('ec2')

        # Retrieve instance objects using the InstanceId
        manager_list = [ec2_resource.Instance(instance['InstanceId']) for instance in response['Instances']]
        manager = manager_list[0]

        manager.wait_until_running()
        manager.reload()

        print(f"Manager launched IP: {manager.public_ip_address }   ID: {manager.id}")
        with open('manager_ip.txt', 'w') as file:
            file.write(manager.public_ip_address )

        return manager

    except ClientError as e:
        print(f"Error launching instances: {e}")
        sys.exit(1)

def transfer_master_status_new(manager, bastion, key_file):
    try:
        # Wait to ensure that instances are fully up and running (optional)
        #time.sleep(120)

        # Initialize SSH client for bastion host
        ssh = paramiko.SSHClient()
        ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())

        # Connect to the bastion host
        ssh.connect(bastion.public_ip_address, username='ubuntu', key_filename=key_file)

        # Get the transport object from the SSH connection
        transport = ssh.get_transport()

        # Define destination (manager's private IP) and local address (bastion's private IP)
        dest_addr = (manager.private_ip_address, 22)
        print(f"Manager public: {manager.public_ip_address}, private: {manager.private_ip_address}")
        local_addr = (bastion.private_ip_address, 22)
        print(f"Bastion public: {bastion.public_ip_address}, private: {bastion.private_ip_address}")

        # Create a channel to the manager instance
        channel = transport.open_channel("direct-tcpip", dest_addr, local_addr)

        # Now create an SFTP session over the channel
        sftp = paramiko.SFTPClient.from_transport(channel)

        # Retrieve the file from the manager instance
        sftp.get('/home/ubuntu/master_status.txt', 'master_status.txt')

        # Clean up
        sftp.close()
        ssh.close()

        # Read and process the retrieved file
        with open('master_status.txt', 'r') as f:
            content = f.read()

        log_file = content.split("File: ")[1].split("\n")[0]
        log_pos = content.split("Position: ")[1].split("\n")[0]

        print(f"Retrieved log_file: {log_file}, log_pos: {log_pos}")
        return log_file, log_pos

    except paramiko.SSHException as e:
        print(f"SSH connection error: {e}")
        sys.exit(1)
    except Exception as e:
        print(f"Error transferring file: {e}")
        sys.exit(1)

def transfer_master_status(manager, key_file):
    try:
        time.sleep(120)
        ssh = paramiko.SSHClient()
        ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        ssh.connect(manager.public_ip_address, username='ubuntu', key_filename=key_file)
        scp = paramiko.SFTPClient.from_transport(ssh.get_transport())
        scp.get('/home/ubuntu/master_status.txt', 'master_status.txt')
        scp.close()
        ssh.close()

        with open('master_status.txt', 'r') as f:
            content = f.read()
        log_file = content.split("File: ")[1].split("\n")[0]
        log_pos = content.split("Position: ")[1].split("\n")[0]

        print(f"Retreived log_file: {log_file}, log_pos: {log_pos}")
        return log_file, log_pos

    except ClientError as e:
        print(f"Error transfering file: {e}")
        sys.exit(1)

def launch_proxy(ec2_client, image_id, instance_type, key_name, security_group_id, subnet_id, manager_ip, workers_ip):
    user_data_script = '''#!/bin/bash
                            sudo apt update -y
                            sudo apt install -y python3-pip python3-venv
                            cd /home/ubuntu
                            python3 -m venv venv
                            echo "source venv/bin/activate" >> /home/ubuntu/.bashrc
                            source venv/bin/activate

                            pip3 install flask requests redis
                            
                            
                            # Wait for the manager_ip.txt file to be transferred
                            while [ ! -f /home/ubuntu/manager_ip.txt ]; do
                                sleep 1
                            done
                            
                             Wait for the workers_ip.txt file to be transferred
                            while [ ! -f /home/ubuntu/workers_ip.txt ]; do
                                sleep 1
                            done
                            
                            # Wait for the proxy.py file to be transferred
                            while [ ! -f /home/ubuntu/proxy.py ]; do
                                sleep 5
                            done

                            python3 proxy.py
                            '''
    try:
        response = ec2_client.run_instances(
            ImageId=image_id,
            MinCount=1,
            MaxCount=1,
            InstanceType=instance_type,
            KeyName=key_name,
            SecurityGroupIds=[security_group_id],
            SubnetId=subnet_id,
            UserData=user_data_script,
            TagSpecifications=[
                {
                    'ResourceType': 'instance',
                    'Tags': [
                        {
                            'Key': 'Name',
                            'Value': 'LabInstance'
                        }
                    ]
                }
            ]
        )

        ec2_resource = boto3.resource('ec2')

        # Retrieve instance objects using the InstanceId
        proxy_list = [ec2_resource.Instance(instance['InstanceId']) for instance in response['Instances']]
        proxy = proxy_list[0]

        proxy.wait_until_running()
        proxy.reload()

        print(f"Proxy launched IP: {proxy.public_ip_address}   ID: {proxy.id}")
        with open('proxy_ip.txt', 'w') as file:
            file.write(proxy.public_ip_address )
        return proxy

    except Exception as e:
        print(f"Error launching instances: {e}")
        sys.exit(1)

def transfer_files(instance, key_file, files_dict):
    try:
        ssh = paramiko.SSHClient()
        ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        ssh.connect(instance.public_ip_address, username='ubuntu', key_filename=key_file)

        scp = paramiko.SFTPClient.from_transport(ssh.get_transport())

        for file in files_dict:
            scp.put(f'{file}', f'/home/ubuntu/{file}')
        scp.close()
        ssh.close()

        print("Files transferred")

    except Exception as e:
        print(f"Error transfering proxy file: {e}")
        sys.exit(1)

def launch_gatekeeper(ec2_client, image_id, instance_type, key_name, security_group_id, subnet_id):
    user_data_script = '''#!/bin/bash 
                                    # Update and install MySQL
                                    sudo apt update -y

                                    sudo apt install -y python3-pip python3-venv
                                    cd /home/ubuntu
                                    python3 -m venv venv
                                    echo "source venv/bin/activate" >> /home/ubuntu/.bashrc
                                    source venv/bin/activate

                                    pip3 install flask requests redis
                                    sudo chown -R ubuntu:ubuntu /home/ubuntu/venv

                                # Wait for the trusted_host_ip.txt file to be transferred
                                while [ ! -f /home/ubuntu/trusted_host_ip.txt ]; do
                                    sleep 5
                                done

                                # Wait for the gatekeeper.py file to be transferred
                                while [ ! -f /home/ubuntu/gatekeeper.py ]; do
                                    sleep 5
                                done
                                
                                python3 -m venv venv
                                echo "source venv/bin/activate" >> /home/ubuntu/.bashrc
                                source venv/bin/activate
                                python3 gatekeeper.py
                                    '''

    try:
        response = ec2_client.run_instances(
            ImageId=image_id,
            MinCount=1,
            MaxCount=1,
            InstanceType=instance_type,
            KeyName=key_name,
            SecurityGroupIds=[security_group_id],
            SubnetId=subnet_id,
            UserData=user_data_script,
            TagSpecifications=[
                {
                    'ResourceType': 'instance',
                    'Tags': [
                        {
                            'Key': 'Name',
                            'Value': 'LabInstance'
                        }
                    ]
                }
            ]
        )

        ec2_resource = boto3.resource('ec2')

        # Retrieve instance objects using the InstanceId
        gatekeeper_list = [ec2_resource.Instance(instance['InstanceId']) for instance in response['Instances']]
        gatekeeper = gatekeeper_list[0]

        gatekeeper.wait_until_running()
        gatekeeper.reload()

        print(f"Gatekeeper launched IP: {gatekeeper.public_ip_address}   ID: {gatekeeper.id}")
        return gatekeeper

    except ClientError as e:
        print(f"Error launching instances: {e}")
        sys.exit(1)

def launch_trusted_host(ec2_client, image_id, instance_type, key_name, security_group_id, subnet_id):
    user_data_script = '''#!/bin/bash 
                                        # Update and install MySQL
                                        sudo apt update -y

                                        sudo apt install -y python3-pip python3-venv
                                        cd /home/ubuntu
                                        python3 -m venv venv
                                        echo "source venv/bin/activate" >> /home/ubuntu/.bashrc
                                        source venv/bin/activate

                                        pip3 install flask requests redis
                                        sudo chown -R ubuntu:ubuntu /home/ubuntu/venv

                                    # Wait for the proxy_ip.txt file to be transferred
                                    while [ ! -f /home/ubuntu/proxy_ip.txt ]; do
                                        sleep 5
                                    done

                                        # Wait for the trusted_host.py file to be transferred
                                    while [ ! -f /home/ubuntu/trusted_host.py ]; do
                                        sleep 5
                                    done
                                    python3 -m venv venv
                                    echo "source venv/bin/activate" >> /home/ubuntu/.bashrc
                                    source venv/bin/activate
                                    python3 trusted_host.py
                                        '''

    try:
        response = ec2_client.run_instances(
            ImageId=image_id,
            MinCount=1,
            MaxCount=1,
            InstanceType=instance_type,
            KeyName=key_name,
            SecurityGroupIds=[security_group_id],
            SubnetId=subnet_id,
            UserData=user_data_script,
            TagSpecifications=[
                {
                    'ResourceType': 'instance',
                    'Tags': [
                        {
                            'Key': 'Name',
                            'Value': 'LabInstance'
                        }
                    ]
                }
            ]
        )

        ec2_resource = boto3.resource('ec2')

        # Retrieve instance objects using the InstanceId
        trusted_host_list = [ec2_resource.Instance(instance['InstanceId']) for instance in response['Instances']]
        trusted_host = trusted_host_list[0]

        trusted_host.wait_until_running()
        trusted_host.reload()

        print(f"Trusted Host launched IP: {trusted_host.public_ip_address}   ID: {trusted_host.id}")
        with open('trusted_host_ip.txt', 'w') as file:
            file.write(trusted_host.public_ip_address )
        return trusted_host

    except ClientError as e:
        print(f"Error launching instances: {e}")
        sys.exit(1)


def main():
    try:
        # Initialize EC2 and ELB clients
        ec2_client = boto3.client('ec2')
        elbv2_client = boto3.client('elbv2')
        num_of_workers = 2

        # Define essential AWS configuration
        vpc_id = get_vpc_id(ec2_client)
        image_id = 'ami-0e86e20dae9224db8'

        # Get key pair, security group, and subnet
        key_name = get_key_pair(ec2_client)
        key_file_path = os.path.join(os.path.expanduser('~/.aws'), f"{key_name}.pem")
        security_group_public = create_security_group(ec2_client, vpc_id, "public")
        security_group_private = create_security_group(ec2_client, vpc_id, "private")
        subnet_public, subnet_private = get_subnet(ec2_client, vpc_id)

        #igw_id = create_internet_gateway(ec2_client, vpc_id)
        #create_route(ec2_client, vpc_id, subnet_public, igw_id)

        #bastion = launch_bastion(ec2_client, image_id, "t2.micro", key_name, security_group_public, subnet_public)

        manager = launch_manager(ec2_client, image_id, "t2.micro", key_name, security_group_private, subnet_private)
        log_file, log_pos = transfer_master_status(manager, key_file_path)

        worker_instances = []
        for i in range(num_of_workers):
            worker = launch_workers(ec2_client, image_id, "t2.micro", key_name, security_group_private,
                           subnet_private, num_of_workers, manager.public_ip_address, log_file, log_pos)
            worker_instances.append(worker)
        with open('workers_ip.txt', 'w') as file:
            file.write(f"{worker_instances[0].public_ip_address} {worker_instances[1].public_ip_address}\n")

        time.sleep(60)
        for instance in [manager, worker_instances[0], worker_instances[1]]:
            transfer_files(instance, key_file_path, ['worker_manager_app.py'])

        gatekeeper = launch_gatekeeper(ec2_client, image_id, "t2.large", key_name,
                                       security_group_public, subnet_public)
        trusted_host = launch_trusted_host(ec2_client, image_id, "t2.large", key_name,
                                           security_group_private, subnet_private)
        proxy = launch_proxy(ec2_client, image_id, "t2.large", key_name,
                             security_group_public, subnet_public, manager.public_ip_address,
                             [worker_instances[0].public_ip_address, worker_instances[1].public_ip_address])
        time.sleep(60)
        transfer_files(gatekeeper, key_file_path, ['gatekeeper.py', 'trusted_host_ip.txt'])
        transfer_files(trusted_host, key_file_path, ['trusted_host.py', 'proxy_ip.txt'])
        transfer_files(proxy, key_file_path, ['manager_ip.txt', 'workers_ip.txt', 'proxy.py'])


    except Exception as e:
        print(f"Error during execution: {e}")

if __name__ == "__main__":
    main()
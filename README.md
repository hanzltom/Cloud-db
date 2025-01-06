Cloud Architecture with Database

## Introduction

The main task of this project is to set up a MySQL cluster on Amazon EC2 and define a complete cloud architecture to simplify the connection process to the database. Additional instances are set up for smooth operations to ensure requests are correct and secure.

---

## App Setup

### Manager Instance
- Acts as the master node for the database.  
- Handles all `WRITE` requests (e.g., `INSERT`, `DELETE`) and specific `READ` requests if configured.  
- MySQL is used with the Sakila database and runs a Python script to execute queries received on port 5000.  

### Worker Instances
- Function as slave nodes replicating the manager’s database for consistency.  
- Handle most `READ` requests.  

### Sysbench Benchmarking
- Sysbench was installed on the manager and worker instances to test database performance.  
- Benchmarking results confirm the setup correctness.

### Proxy Instance
- Routes incoming requests to the manager and worker instances.  
- Strategies for handling `READ` requests:  
  1. **Direct Hit**: Forward to the manager.  
  2. **Random**: Select a random worker.  
  3. **Customized**: Choose the worker with the quickest response time.  
  4. **Round Robin** (default).  

### Trusted Host Instance
- Adds a security layer by validating requests before forwarding them to the proxy.  
- Protects against SQL injection and enforces query restrictions.

### Gatekeeper Instance
- The only internet-facing instance.  
- Validates non-empty queries before forwarding them to the trusted host.  

### Security Groups and Subnets
- **Public Subnet**: Hosts the gatekeeper (CIDR block: `172.31.1.0/24`).  
- **Private Subnet**: Hosts other instances (CIDR block: `172.31.2.0/24`).  
- Security groups ensure communication is limited to internal channels.  

### Benchmarking
- A benchmarking script tests the architecture with 1000 `INSERT` and `SELECT` queries.  
- Measures performance for each proxy strategy.

---

## Instructions to Run the Code

1. **Create a VPC and Subnets**:  
   - VPC CIDR block: `172.31.0.0/16`.  
   - Public Subnet CIDR block: `172.31.1.0/24`.  
   - Private Subnet CIDR block: `172.31.2.0/24`.  
   - Configure routing tables and internet gateways.  

2. **Install Python and Boto3**:  
   - Ensure Python and AWS SDK (Boto3) are installed.  

3. **Clone the repo**:  
   - Download and extract provided files.  

4. **Insert AMI Image ID**:  
   - Update the code with the appropriate AMI image ID.  

5. **Make the Script Executable**:  
   ```bash
   chmod +x manage_cloud.sh

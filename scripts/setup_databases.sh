#!/bin/bash

# PerfectMPC Database Setup Script

set -e

echo "Setting up PerfectMPC databases..."

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Function to print colored output
print_status() {
    echo -e "${GREEN}[INFO]${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

print_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# Check if running as root
if [[ $EUID -ne 0 ]]; then
   print_error "This script must be run as root"
   exit 1
fi

# Configure Redis
print_status "Configuring Redis..."

# Backup original Redis config
if [ ! -f "/etc/redis/redis.conf.backup" ]; then
    cp /etc/redis/redis.conf /etc/redis/redis.conf.backup
    print_status "Redis config backed up"
fi

# Configure Redis for MPC usage
cat >> /etc/redis/redis.conf << EOF

# PerfectMPC Configuration
maxmemory 256mb
maxmemory-policy allkeys-lru
save 900 1
save 300 10
save 60 10000
EOF

# Restart Redis to apply changes
systemctl restart redis-server
print_status "Redis configured and restarted"

# Configure MongoDB
print_status "Configuring MongoDB..."

# Backup original MongoDB config
if [ ! -f "/etc/mongod.conf.backup" ]; then
    cp /etc/mongod.conf /etc/mongod.conf.backup
    print_status "MongoDB config backed up"
fi

# Configure MongoDB for MPC usage
cat > /etc/mongod.conf << EOF
# mongod.conf for PerfectMPC

# Where to store data
storage:
  dbPath: /var/lib/mongodb
  journal:
    enabled: true

# Where to write logging data
systemLog:
  destination: file
  logAppend: true
  path: /var/log/mongodb/mongod.log

# Network interfaces
net:
  port: 27017
  bindIp: 127.0.0.1

# Process management
processManagement:
  timeZoneInfo: /usr/share/zoneinfo

# Security (disabled for single user setup)
#security:
#  authorization: enabled

# Operation profiling
operationProfiling:
  slowOpThresholdMs: 100
  mode: slowOp

# Replication (disabled for single instance)
#replication:
#  replSetName: "rs0"

# Sharding (disabled for single instance)
#sharding:
#  clusterRole: configsvr
EOF

# Restart MongoDB to apply changes
systemctl restart mongod
print_status "MongoDB configured and restarted"

# Wait for services to start
print_status "Waiting for services to start..."
sleep 5

# Test Redis connection
print_status "Testing Redis connection..."
if redis-cli ping | grep -q "PONG"; then
    print_status "Redis is running and responding"
else
    print_error "Redis is not responding"
    exit 1
fi

# Test MongoDB connection
print_status "Testing MongoDB connection..."
if mongosh --eval "db.adminCommand('ping')" --quiet | grep -q "ok"; then
    print_status "MongoDB is running and responding"
else
    print_error "MongoDB is not responding"
    exit 1
fi

# Initialize MongoDB database
print_status "Initializing MongoDB database..."
mongosh --eval "
use perfectmpc;
db.createCollection('sessions');
db.createCollection('code_history');
db.createCollection('documents');
db.createCollection('embeddings');
db.createCollection('improvements');
db.createCollection('analytics');

// Create indexes
db.sessions.createIndex({'session_id': 1}, {unique: true});
db.sessions.createIndex({'timestamp': 1});
db.code_history.createIndex({'session_id': 1, 'timestamp': -1});
db.documents.createIndex({'doc_id': 1}, {unique: true});
db.documents.createIndex({'session_id': 1});
db.embeddings.createIndex({'doc_id': 1, 'chunk_id': 1}, {unique: true});
db.improvements.createIndex({'session_id': 1, 'timestamp': -1});
db.analytics.createIndex({'timestamp': -1});

print('Database and collections created successfully');
"

print_status "MongoDB database initialized"

# Set up Redis keys for testing
print_status "Setting up Redis test data..."
redis-cli SET "mpc:test" "PerfectMPC Redis is working"
redis-cli EXPIRE "mpc:test" 3600

# Create backup script
print_status "Creating backup script..."
cat > /opt/PerfectMPC/scripts/backup_databases.sh << 'EOF'
#!/bin/bash

# Database backup script for PerfectMPC

BACKUP_DIR="/opt/PerfectMPC/backups"
DATE=$(date +%Y%m%d_%H%M%S)

echo "Starting database backup..."

# Backup MongoDB
echo "Backing up MongoDB..."
mongodump --db perfectmpc --out "$BACKUP_DIR/mongodb/backup_$DATE"
tar -czf "$BACKUP_DIR/mongodb/perfectmpc_$DATE.tar.gz" -C "$BACKUP_DIR/mongodb" "backup_$DATE"
rm -rf "$BACKUP_DIR/mongodb/backup_$DATE"

# Backup Redis
echo "Backing up Redis..."
redis-cli BGSAVE
sleep 2
cp /var/lib/redis/dump.rdb "$BACKUP_DIR/redis/dump_$DATE.rdb"

# Backup ChromaDB
echo "Backing up ChromaDB..."
if [ -d "/opt/PerfectMPC/data/chromadb" ]; then
    tar -czf "$BACKUP_DIR/chromadb/chromadb_$DATE.tar.gz" -C "/opt/PerfectMPC/data" chromadb
fi

# Clean old backups (keep last 7 days)
find "$BACKUP_DIR" -name "*.tar.gz" -mtime +7 -delete
find "$BACKUP_DIR" -name "*.rdb" -mtime +7 -delete

echo "Backup completed: $DATE"
EOF

chmod +x /opt/PerfectMPC/scripts/backup_databases.sh

# Create restore script
print_status "Creating restore script..."
cat > /opt/PerfectMPC/scripts/restore_databases.sh << 'EOF'
#!/bin/bash

# Database restore script for PerfectMPC

if [ $# -eq 0 ]; then
    echo "Usage: $0 <backup_date>"
    echo "Example: $0 20231224_143000"
    exit 1
fi

BACKUP_DIR="/opt/PerfectMPC/backups"
DATE=$1

echo "Restoring databases from backup: $DATE"

# Restore MongoDB
if [ -f "$BACKUP_DIR/mongodb/perfectmpc_$DATE.tar.gz" ]; then
    echo "Restoring MongoDB..."
    cd "$BACKUP_DIR/mongodb"
    tar -xzf "perfectmpc_$DATE.tar.gz"
    mongorestore --db perfectmpc --drop "backup_$DATE/perfectmpc"
    rm -rf "backup_$DATE"
    echo "MongoDB restored"
else
    echo "MongoDB backup not found: perfectmpc_$DATE.tar.gz"
fi

# Restore Redis
if [ -f "$BACKUP_DIR/redis/dump_$DATE.rdb" ]; then
    echo "Restoring Redis..."
    systemctl stop redis-server
    cp "$BACKUP_DIR/redis/dump_$DATE.rdb" /var/lib/redis/dump.rdb
    chown redis:redis /var/lib/redis/dump.rdb
    systemctl start redis-server
    echo "Redis restored"
else
    echo "Redis backup not found: dump_$DATE.rdb"
fi

# Restore ChromaDB
if [ -f "$BACKUP_DIR/chromadb/chromadb_$DATE.tar.gz" ]; then
    echo "Restoring ChromaDB..."
    rm -rf "/opt/PerfectMPC/data/chromadb"
    tar -xzf "$BACKUP_DIR/chromadb/chromadb_$DATE.tar.gz" -C "/opt/PerfectMPC/data"
    chown -R mpc:mpc "/opt/PerfectMPC/data/chromadb"
    echo "ChromaDB restored"
else
    echo "ChromaDB backup not found: chromadb_$DATE.tar.gz"
fi

echo "Restore completed"
EOF

chmod +x /opt/PerfectMPC/scripts/restore_databases.sh

# Set up daily backup cron job
print_status "Setting up daily backup cron job..."
(crontab -l 2>/dev/null; echo "0 2 * * * /opt/PerfectMPC/scripts/backup_databases.sh >> /opt/PerfectMPC/logs/backup.log 2>&1") | crontab -

# Display status
print_status "Database setup completed!"
print_status "Redis status:"
systemctl status redis-server --no-pager -l

print_status "MongoDB status:"
systemctl status mongod --no-pager -l

print_status "Database configuration summary:"
echo "- Redis: localhost:6379 (no auth)"
echo "- MongoDB: localhost:27017 (no auth)"
echo "- Database: perfectmpc"
echo "- Backup script: /opt/PerfectMPC/scripts/backup_databases.sh"
echo "- Restore script: /opt/PerfectMPC/scripts/restore_databases.sh"
echo "- Daily backup: 2:00 AM via cron"

print_status "Database setup script finished!"

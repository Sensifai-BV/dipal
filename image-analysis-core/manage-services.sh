#!/bin/bash

# PhotoGear Image Analysis Services Manager
# This script helps manage individual or all services

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Service definitions
declare -A SERVICES=(
    ["gateway"]="docker-compose.api-gateway.yml"
    ["calibration"]="docker-compose.calibration.yml"
    ["sfm"]="docker-compose.sfm.yml"
    ["orthomosaic"]="docker-compose.orthomosaic.yml"
    ["all"]="docker-compose.yml"
)

print_usage() {
    echo "Usage: $0 {start|stop|restart|logs|status} {all|gateway|calibration|sfm|orthomosaic}"
    echo ""
    echo "Commands:"
    echo "  start       - Start service(s)"
    echo "  stop        - Stop service(s)"
    echo "  restart     - Restart service(s)"
    echo "  logs        - Show logs for service(s)"
    echo "  status      - Show status of service(s)"
    echo "  build       - Build service(s)"
    echo ""
    echo "Services:"
    echo "  all         - All services (API Gateway + processing services)"
    echo "  gateway     - API Gateway only (port 8080)"
    echo "  calibration - Radiometric Calibration service (port 8001)"
    echo "  sfm         - Structure from Motion service (port 8002)"
    echo "  orthomosaic - Orthomosaic Generation service (port 8003)"
    echo ""
    echo "Examples:"
    echo "  $0 start all              # Start all services"
    echo "  $0 start gateway          # Start only API Gateway"
    echo "  $0 logs sfm               # Show SFM service logs"
    echo "  $0 restart calibration    # Restart calibration service"
}

check_network() {
    if ! docker network inspect image_processing_network >/dev/null 2>&1; then
        echo -e "${YELLOW}Creating Docker network 'image_processing_network'...${NC}"
        docker network create image_processing_network
    fi
}

check_env() {
    if [ ! -f .env ]; then
        echo -e "${YELLOW}Warning: .env file not found. Creating from .env.example...${NC}"
        if [ -f .env.example ]; then
            cp .env.example .env
            echo -e "${GREEN}.env file created. Please review and update if needed.${NC}"
        else
            echo -e "${RED}Error: .env.example not found${NC}"
            exit 1
        fi
    fi
}

get_compose_file() {
    local service=$1
    if [ -z "${SERVICES[$service]}" ]; then
        echo -e "${RED}Error: Unknown service '$service'${NC}"
        print_usage
        exit 1
    fi
    echo "${SERVICES[$service]}"
}

start_service() {
    local service=$1
    local compose_file=$(get_compose_file $service)
    
    check_network
    check_env
    
    echo -e "${GREEN}Starting $service...${NC}"
    docker-compose -f "$compose_file" up -d --build
    echo -e "${GREEN}$service started successfully${NC}"
}

stop_service() {
    local service=$1
    local compose_file=$(get_compose_file $service)
    
    echo -e "${YELLOW}Stopping $service...${NC}"
    docker-compose -f "$compose_file" down
    echo -e "${GREEN}$service stopped${NC}"
}

restart_service() {
    local service=$1
    stop_service $service
    start_service $service
}

logs_service() {
    local service=$1
    local compose_file=$(get_compose_file $service)
    
    echo -e "${GREEN}Showing logs for $service (Ctrl+C to exit)...${NC}"
    docker-compose -f "$compose_file" logs -f
}

status_service() {
    local service=$1
    local compose_file=$(get_compose_file $service)
    
    echo -e "${GREEN}Status for $service:${NC}"
    docker-compose -f "$compose_file" ps
}

build_service() {
    local service=$1
    local compose_file=$(get_compose_file $service)
    
    echo -e "${GREEN}Building $service...${NC}"
    docker-compose -f "$compose_file" build
    echo -e "${GREEN}$service built successfully${NC}"
}

# Main script logic
if [ $# -lt 2 ]; then
    print_usage
    exit 1
fi

COMMAND=$1
SERVICE=$2

case $COMMAND in
    start)
        start_service $SERVICE
        ;;
    stop)
        stop_service $SERVICE
        ;;
    restart)
        restart_service $SERVICE
        ;;
    logs)
        logs_service $SERVICE
        ;;
    status)
        status_service $SERVICE
        ;;
    build)
        build_service $SERVICE
        ;;
    *)
        echo -e "${RED}Error: Unknown command '$COMMAND'${NC}"
        print_usage
        exit 1
        ;;
esac

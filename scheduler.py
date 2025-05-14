import time
import subprocess
import logging
from datetime import datetime

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('odds_scheduler.log'),
        logging.StreamHandler()
    ]
)

def run_fetch_odds():
    """Run the fetch_odds.py script"""
    try:
        logging.info("Starting odds fetch...")
        result = subprocess.run(['python', 'fetch_odds.py'], 
                               capture_output=True, 
                               text=True, 
                               check=True)
        logging.info(f"Fetch completed successfully: {result.stdout}")
        return True
    except subprocess.CalledProcessError as e:
        logging.error(f"Error running fetch_odds.py: {e}")
        logging.error(f"STDOUT: {e.stdout}")
        logging.error(f"STDERR: {e.stderr}")
        return False
    except Exception as e:
        logging.error(f"Unexpected error: {e}")
        return False

def main():
    """Main function to run the scheduler"""
    logging.info("Starting odds scheduler")
    
    # Run immediately on startup
    run_fetch_odds()
    
    # Schedule to run every 5 minutes
    interval_seconds = 5 * 60  # 5 minutes
    
    try:
        while True:
            next_run = datetime.now().timestamp() + interval_seconds
            logging.info(f"Next run scheduled at: {datetime.fromtimestamp(next_run).strftime('%Y-%m-%d %H:%M:%S')}")
            
            # Sleep until next run time
            time.sleep(interval_seconds)
            
            # Run the fetch script
            run_fetch_odds()
    except KeyboardInterrupt:
        logging.info("Scheduler stopped by user")
    except Exception as e:
        logging.error(f"Scheduler error: {e}")

if __name__ == "__main__":
    main()
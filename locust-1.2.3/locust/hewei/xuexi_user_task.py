import logging

def hw_log():
    logging.basicConfig(level = logging.INFO,format = '%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    logger = logging.getLogger(__name__)
    return logger
 
logger = hw_log()

logger.info("Start print log")
logger.debug("Do something")
logger.warning("Something maybe fail.")

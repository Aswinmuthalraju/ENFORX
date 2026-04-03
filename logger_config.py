import logging
import json
import logging.handlers
import sys
from datetime import datetime
import os

_LOG_DIR = os.path.join(os.path.dirname(__file__), "logs")

# ANSI colours
class Colors:
    G   = "\033[92m"   # green
    R   = "\033[91m"   # red
    Y   = "\033[93m"   # yellow
    B   = "\033[94m"   # blue
    DIM = "\033[2m"
    RST = "\033[0m"

_STATUS_ICON = {
    "PASS":                 f"{Colors.G}✅ PASS{Colors.RST}   ",
    "BLOCK":                f"{Colors.R}❌ BLOCK{Colors.RST}  ",
    "ALLOW":                f"{Colors.G}✅ ALLOW{Colors.RST}  ",
    "CORRECT":              f"{Colors.Y}🛠  CORRECT{Colors.RST}",
    "ALIGNED":              f"{Colors.G}✅ ALIGNED{Colors.RST}",
    "MISALIGNED":           f"{Colors.R}❌ MIS{Colors.RST}    ",
    "PROCEED":              f"{Colors.G}✅ PROCEED{Colors.RST}",
    "MODIFY":               f"{Colors.Y}🔄 MODIFY{Colors.RST} ",
    "FLAG":                 f"{Colors.Y}⚠  FLAG{Colors.RST}   ",
    "AUTHORIZED":           f"{Colors.G}✅ AUTH{Colors.RST}   ",
    "DELEGATION_VIOLATION": f"{Colors.R}🚫 DAP{Colors.RST}    ",
    "EXECUTE":              f"{Colors.G}🚀 EXECUTE{Colors.RST} ",
    "EMERGENCY_BLOCK":      f"{Colors.R}🚨 EMERGENCY{Colors.RST}",
    "SIMULATED":            f"{Colors.B}🔵 SIMULATED{Colors.RST}",
}

class JsonFormatter(logging.Formatter):
    def format(self, record):
        msg = record.getMessage()
        if hasattr(record, "json_dict"):
            data = record.json_dict
        else:
            data = {
                "timestamp": datetime.fromtimestamp(record.created).isoformat(),
                "layer": record.name,
                "level": record.levelname,
                "message": msg
            }
        return json.dumps(data)

class TextFormatter(logging.Formatter):
    def format(self, record):
        dt = datetime.fromtimestamp(record.created).strftime("%Y-%m-%d %H:%M:%S")
        return f"{dt} | {record.levelname:<8} | {record.name} | {record.getMessage()}"

class ColorTerminalFormatter(logging.Formatter):
    def format(self, record):
        dt = datetime.fromtimestamp(record.created).strftime("%H:%M:%S")
        if hasattr(record, "status_icon"):
            status = record.status_icon
            return f"{dt} | {status} | {record.name:<17} | {record.getMessage()}"
        return f"{dt} | {record.levelname:<9} | {record.name:<17} | {record.getMessage()}"

def setup_logging():
    if not os.path.exists(_LOG_DIR):
        os.makedirs(_LOG_DIR)
        
    date_str = datetime.now().strftime("%Y%m%d")
    log_file = os.path.join(_LOG_DIR, f"enforx_{date_str}.log")
    json_file = os.path.join(_LOG_DIR, f"enforx_{date_str}.json")
    
    root_logger = logging.getLogger()
    root_logger.setLevel(logging.INFO)
    root_logger.handlers = [] # clear any existing
    
    # 1. Text File Handler
    txt_handler = logging.handlers.TimedRotatingFileHandler(log_file, when="midnight", interval=1, backupCount=7)
    txt_handler.setFormatter(TextFormatter())
    
    # 2. JSON File Handler
    class JsonFilter(logging.Filter):
        def filter(self, record):
            return True # allow all
            
    json_handler = logging.handlers.TimedRotatingFileHandler(json_file, when="midnight", interval=1, backupCount=7)
    json_handler.setFormatter(JsonFormatter())
    json_handler.addFilter(JsonFilter())
    
    # 3. Terminal Handler
    console = logging.StreamHandler(sys.stdout)
    console.setFormatter(ColorTerminalFormatter())

    root_logger.addHandler(txt_handler)
    root_logger.addHandler(json_handler)
    root_logger.addHandler(console)
    
def get_layer_logger(name):
    return logging.getLogger(name)

def log_layer_result(layer: int, name: str, status: str, detail: str = ""):
    logger_name = f"layer.{layer:02d}.{name.lower().replace(' ', '_')}"
    logger = logging.getLogger(logger_name)
    level = logging.WARNING if "BLOCK" in status or "VIOLATION" in status or "MISALIGNED" in status or "FLAG" in status else logging.INFO
    icon = _STATUS_ICON.get(status, f"{Colors.DIM}{status}{Colors.RST}")
    
    # Create the structured data dict
    data = {
        "timestamp": datetime.now().isoformat(),
        "layer": logger_name,
        "level": logging.getLevelName(level),
        "status": status,
        "detail": detail
    }
    
    extra = {"json_dict": data, "status_icon": icon}
    logger.log(level, detail or status, extra=extra)

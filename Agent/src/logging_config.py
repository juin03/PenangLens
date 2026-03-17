"""
Logging and observability configuration for PenangLens AI Agent.

Sets up:
1. Structured logging with JSON format for production
2. Pretty console logging for development
3. LangSmith tracing integration (optional)
"""

import os
import sys
import logging
import json
from datetime import datetime, timezone


class JSONFormatter(logging.Formatter):
    """JSON log formatter for structured logging in production."""
    
    def format(self, record):
        log_entry = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        
        # Add extra fields if present
        extra_fields = [
            "thread_id",
            "tool_name",
            "duration_ms",
            "correlation_id",
            "request_id",
            "method",
            "path",
            "status_code",
            "client_ip",
            "event",
            "retry_after_s",
            "is_quota_error",
            "google_api_key_set",
            "google_api_key_preview",
            "google_maps_key_set",
            "google_maps_key_preview",
            "azure_search_endpoint_set",
            "azure_search_key_set",
            "azure_search_key_preview",
            "log_level",
        ]
        for field in extra_fields:
            if hasattr(record, field):
                log_entry[field] = getattr(record, field)
            
        if record.exc_info and record.exc_info[0] is not None:
            log_entry["exception"] = self.formatException(record.exc_info)
            
        return json.dumps(log_entry, default=str)


class PrettyFormatter(logging.Formatter):
    """Colorized console formatter for development."""
    
    COLORS = {
        "DEBUG": "\033[36m",     # Cyan
        "INFO": "\033[32m",      # Green
        "WARNING": "\033[33m",   # Yellow
        "ERROR": "\033[31m",     # Red
        "CRITICAL": "\033[35m",  # Magenta
    }
    RESET = "\033[0m"
    
    def format(self, record):
        color = self.COLORS.get(record.levelname, self.RESET)
        timestamp = datetime.now().strftime("%H:%M:%S")
        
        prefix = f"{color}[{timestamp}] {record.levelname:<8}{self.RESET}"
        message = record.getMessage()
        
        # Add context fields
        extras = []
        if hasattr(record, "thread_id"):
            extras.append(f"thread={record.thread_id[:8]}")
        if hasattr(record, "request_id") and record.request_id:
            extras.append(f"req={str(record.request_id)[:8]}")
        if hasattr(record, "method") and hasattr(record, "path"):
            extras.append(f"{record.method} {record.path}")
        if hasattr(record, "status_code"):
            extras.append(f"status={record.status_code}")
        if hasattr(record, "client_ip"):
            extras.append(f"ip={record.client_ip}")
        if hasattr(record, "tool_name"):
            extras.append(f"tool={record.tool_name}")
        if hasattr(record, "duration_ms"):
            extras.append(f"took={record.duration_ms}ms")
        if hasattr(record, "retry_after_s") and record.retry_after_s is not None:
            extras.append(f"retry={record.retry_after_s}s")
        if hasattr(record, "is_quota_error") and record.is_quota_error:
            extras.append("quota_exhausted=true")
        if hasattr(record, "google_api_key_preview"):
            extras.append(f"gemini_key={record.google_api_key_preview}")
        if hasattr(record, "google_maps_key_preview"):
            extras.append(f"maps_key={record.google_maps_key_preview}")
        if hasattr(record, "azure_search_key_preview"):
            extras.append(f"azure_key={record.azure_search_key_preview}")
            
        context = f" [{', '.join(extras)}]" if extras else ""
        
        return f"{prefix} {message}{context}"


def setup_logging(level: str = "INFO", json_format: bool = False) -> logging.Logger:
    """
    Configure logging for the application.
    
    Args:
        level: Log level (DEBUG, INFO, WARNING, ERROR)
        json_format: Use JSON format (for production) vs pretty format (for dev)
    
    Returns:
        Root logger for the application
    """
    logger = logging.getLogger("penang_agent")
    logger.setLevel(getattr(logging, level.upper(), logging.INFO))
    
    # Remove existing handlers
    logger.handlers.clear()
    
    # Console handler
    handler = logging.StreamHandler(sys.stdout)
    handler.setLevel(getattr(logging, level.upper(), logging.INFO))
    
    if json_format:
        handler.setFormatter(JSONFormatter())
    else:
        handler.setFormatter(PrettyFormatter())
    
    logger.addHandler(handler)
    
    # Quiet down noisy libraries
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("httpcore").setLevel(logging.WARNING)
    logging.getLogger("urllib3").setLevel(logging.WARNING)
    logging.getLogger("google").setLevel(logging.WARNING)
    
    return logger


def setup_langsmith():
    """
    Configure LangSmith tracing if API key is available.
    
    Set these environment variables to enable:
        LANGCHAIN_API_KEY=your_langsmith_api_key
        LANGCHAIN_TRACING_V2=true
        LANGCHAIN_PROJECT=penang-lens-agent
    """
    logger = logging.getLogger("penang_agent")
    
    api_key = os.getenv("LANGCHAIN_API_KEY")
    if api_key:
        os.environ.setdefault("LANGCHAIN_TRACING_V2", "true")
        os.environ.setdefault("LANGCHAIN_PROJECT", "penang-lens-agent")
        logger.info("LangSmith tracing enabled (project: penang-lens-agent)")
    else:
        logger.debug("LangSmith tracing not configured (no LANGCHAIN_API_KEY)")


def get_logger(name: str = "penang_agent") -> logging.Logger:
    """Get a logger instance."""
    return logging.getLogger(name)

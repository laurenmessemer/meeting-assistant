"""Structured logging utilities for the agent."""

import json
import logging
import uuid
from datetime import datetime
from typing import Dict, Any, Optional
from functools import wraps


class StructuredLogger:
    """Structured logger that outputs JSON logs."""
    
    def __init__(self, name: str = "meeting_assistant"):
        self.logger = logging.getLogger(name)
        self.logger.setLevel(logging.DEBUG)
        
        # Create console handler with JSON formatter
        if not self.logger.handlers:
            handler = logging.StreamHandler()
            handler.setLevel(logging.DEBUG)
            formatter = JSONFormatter()
            handler.setFormatter(formatter)
            self.logger.addHandler(handler)
    
    def _log(self, level: int, message: str, correlation_id: Optional[str] = None, **kwargs):
        """Internal logging method with structured data."""
        log_data = {
            "timestamp": datetime.utcnow().isoformat(),
            "level": logging.getLevelName(level),
            "message": message,
            "correlation_id": correlation_id,
            **kwargs
        }
        self.logger.log(level, json.dumps(log_data))
    
    def info(self, message: str, correlation_id: Optional[str] = None, **kwargs):
        """Log INFO level message."""
        self._log(logging.INFO, message, correlation_id, **kwargs)
    
    def debug(self, message: str, correlation_id: Optional[str] = None, **kwargs):
        """Log DEBUG level message."""
        self._log(logging.DEBUG, message, correlation_id, **kwargs)
    
    def error(self, message: str, correlation_id: Optional[str] = None, **kwargs):
        """Log ERROR level message."""
        self._log(logging.ERROR, message, correlation_id, **kwargs)
    
    def warning(self, message: str, correlation_id: Optional[str] = None, **kwargs):
        """Log WARNING level message."""
        self._log(logging.WARNING, message, correlation_id, **kwargs)


class JSONFormatter(logging.Formatter):
    """JSON formatter for structured logging."""
    
    def format(self, record):
        """Format log record as JSON."""
        # If message is already JSON, return as-is
        if isinstance(record.msg, str) and record.msg.startswith('{'):
            return record.msg
        
        # Otherwise, create JSON structure
        log_data = {
            "timestamp": datetime.utcnow().isoformat(),
            "level": record.levelname,
            "message": record.getMessage(),
            "module": record.module,
            "function": record.funcName,
            "line": record.lineno
        }
        
        # Add any extra fields
        if hasattr(record, 'correlation_id'):
            log_data["correlation_id"] = record.correlation_id
        if hasattr(record, 'duration_ms'):
            log_data["duration_ms"] = record.duration_ms
        if hasattr(record, 'data_shape'):
            log_data["data_shape"] = record.data_shape
        
        return json.dumps(log_data)


def generate_correlation_id() -> str:
    """Generate a unique correlation ID for request tracking."""
    return str(uuid.uuid4())


def log_pipeline_step(func):
    """Decorator to log pipeline step execution with timing."""
    @wraps(func)
    async def async_wrapper(*args, **kwargs):
        correlation_id = kwargs.get('correlation_id') or generate_correlation_id()
        logger = StructuredLogger()
        
        step_name = func.__name__
        logger.info(
            f"Pipeline step started: {step_name}",
            correlation_id=correlation_id,
            step=step_name
        )
        
        start_time = datetime.utcnow()
        try:
            result = await func(*args, **kwargs)
            duration_ms = (datetime.utcnow() - start_time).total_seconds() * 1000
            
            # Log data shape if result is a dict
            data_shape = None
            if isinstance(result, dict):
                data_shape = {k: type(v).__name__ for k, v in result.items()}
            
            logger.info(
                f"Pipeline step completed: {step_name}",
                correlation_id=correlation_id,
                step=step_name,
                duration_ms=duration_ms,
                data_shape=data_shape
            )
            
            return result
        except Exception as e:
            duration_ms = (datetime.utcnow() - start_time).total_seconds() * 1000
            logger.error(
                f"Pipeline step failed: {step_name}",
                correlation_id=correlation_id,
                step=step_name,
                duration_ms=duration_ms,
                error=str(e),
                error_type=type(e).__name__
            )
            raise
    
    @wraps(func)
    def sync_wrapper(*args, **kwargs):
        correlation_id = kwargs.get('correlation_id') or generate_correlation_id()
        logger = StructuredLogger()
        
        step_name = func.__name__
        logger.info(
            f"Pipeline step started: {step_name}",
            correlation_id=correlation_id,
            step=step_name
        )
        
        start_time = datetime.utcnow()
        try:
            result = func(*args, **kwargs)
            duration_ms = (datetime.utcnow() - start_time).total_seconds() * 1000
            
            data_shape = None
            if isinstance(result, dict):
                data_shape = {k: type(v).__name__ for k, v in result.items()}
            
            logger.info(
                f"Pipeline step completed: {step_name}",
                correlation_id=correlation_id,
                step=step_name,
                duration_ms=duration_ms,
                data_shape=data_shape
            )
            
            return result
        except Exception as e:
            duration_ms = (datetime.utcnow() - start_time).total_seconds() * 1000
            logger.error(
                f"Pipeline step failed: {step_name}",
                correlation_id=correlation_id,
                step=step_name,
                duration_ms=duration_ms,
                error=str(e),
                error_type=type(e).__name__
            )
            raise
    
    # Return appropriate wrapper based on function type
    import asyncio
    if asyncio.iscoroutinefunction(func):
        return async_wrapper
    return sync_wrapper


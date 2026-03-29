"""
Writes outputs to log file(s) as well as to the console. Saves
a lot of legwork and does so it style. Color-coded. Nifty!
"""

from logging import DEBUG, INFO, WARNING, ERROR, CRITICAL, \
    StreamHandler, Formatter, Logger, LogRecord, setLoggerClass, getLogger
from logging.handlers import RotatingFileHandler
from pathlib import Path
from functools import wraps
from sys import stdout
from time import time
from typing import Any, TypeVar, Callable, cast

from config.cfg_parser import cfg

F = TypeVar('F', bound = Callable[..., Any])
DEFAULT_LOGGER_NAME = str(cfg('logger', 'logger_name'))
DEFAULT_CONSOLE_LEVEL = int(cfg('logger', 'console_log_level'))
DEFAULT_FILE_LEVEL = int(cfg('logger', 'file_log_level'))
DEFAULT_LOG_DIRECTORY = str(cfg('logger', 'log_file_directory'))

class ColorFormatter(Formatter):

    def __init__(self, *args, **kwargs):
        """Color formatter for console log messages."""

        self.reset_color = "\033[0m"

        self.level_colors = {
            DEBUG: "\033[34m", # Blue
            INFO: "\033[90m", # Grey
            WARNING: "\033[33m", # Yellow
            ERROR: "\033[38;5;208m", # Orange
            CRITICAL: "\033[31m"} #Red

        super().__init__(*args, **kwargs)
        return

    def format(self, record: LogRecord) -> str:
        """Formats the record based on log level."""

        result = super().format(record)
        color = self.level_colors[record.levelno]
        level = f"[{record.levelname}]"
        colored_level = f"{color}{level}{self.reset_color}"
        result = result.replace(level, colored_level)

        # result = result.replace(
        #     f"[{record.levelname}]", 
        #     f"{color}[{record.levelname}] {self.reset_color}")

        return result

class Lumberjack(Logger):
    """
    Lumberjacks. The ultimate loggers. The etymology on this class name is a true rollercoaster.
    """

    def __init__(self, *args, **kwargs):

        super().__init__(*args, **kwargs)

        self.setLevel(DEBUG)

        return

    def setup(self, 
        console_level: int, 
        file_level: int, 
        log_file_dir: str
    ) -> None:
        """
        This process "initializes" the logger in a seperate step so that it
        can play nice with get_logger(), which is predicated on logging.getLogger.
        That function doesn't track whether the returned instance was freshly
        created or pre-existing, so this allows for explicit setup.

        console_log_level: Will only "listen" to logs that meet or beat this level.
        file_log_level: Same but for files. 
        log_file_dir: If blank, no file logging. Makes new log file if need be.
        """

        if self.handlers:
            return

        console_formatter = ColorFormatter(
            fmt='%(asctime)s [%(levelname)s] %(name)s: %(message)s',
            datefmt='%H:%M:%S')

        console_handler = StreamHandler(stdout)
        console_handler.setLevel(console_level)
        console_handler.setFormatter(console_formatter)
        self.addHandler(console_handler)

        if not log_file_dir:
            return

        log_file_dir += ".log"

        if not Path(log_file_dir).exists():
            Path(log_file_dir).parent.mkdir(parents = True, exist_ok = True)

        file_formatter = Formatter(
            fmt = '%(asctime)s [%(levelname)s] %(name)s: %(message)s',
            datefmt = '%D | %H:%M:%S') 

        file_handler = RotatingFileHandler(
            log_file_dir,
            maxBytes = 2**20 * 5, # Five MB i believe?
            backupCount = 7,
            encoding = 'utf-8')
        file_handler.setLevel(file_level)
        file_handler.setFormatter(file_formatter)
        self.addHandler(file_handler)

        self.debug("Logger set up.")

        return

    def internal_log(self,
        level: int = DEBUG, 
        include_args: bool = False,
        announce_start: bool = False
    ) -> Callable[[F], F]:        
        """
        Decorator for logging execution times.
        **level:** what level to report the times as.
        **include_args:** whether to annouce the arguments passed in.
        **announce_start:** if including args, then this is moot. But
            if you just want to know it's began (but the args are
            too long/unimportant), you can turn this on.
        **logger_name:** to pass it through a specific logger. Defaults
            to the logger specified in the config if left blank.

        **->** A decorator. Just use @log_time on top of the function.
        """

        def decorator(func: F) -> F:

            @wraps(func)
            def wrapper(*args: Any, **kwargs: Any) -> Any:
                
                if include_args or announce_start:
                    self.log(level, f"Executing {func.__name__}().")

                if include_args:
                    args_str = ', '.join([str(arg) for arg in args])
                    kwargs_str = ', '.join([f"{k} = {v}" for k, v in kwargs.items()])
                    all_args = f"{args_str}{', ' if args_str and kwargs_str else ''}{kwargs_str}"
                    self.log(level, f"...with the following arguments: ({all_args}).")

                start_time = time()

                try:
                    result = func(*args, **kwargs)
                    execution_time = time() - start_time

                    self.log(level, f"{func.__name__} executed in {execution_time:.4f} seconds.")
                    return result

                except Exception as e:
                    execution_time = time() - start_time
                    self.error(f"{func.__name__} failed after {execution_time:.4f} seconds with error: {str(e)}.")
                    raise

            return cast(F, wrapper)

        return decorator
        
setLoggerClass(Lumberjack)

def get_logger(
    name: str | None = None,
    console_level: int | None = None,
    file_level: int | None = None,
    log_file_dir: str | None = None
) -> Lumberjack:
    """
    Gets you loggin'.
      **name:** to keep distinct the different logger instances.
      **console_level:** Logger only prints to console the
        calls which meet or exceed this level specified here.
      **file_level:** only writes to the log file calls which
        meet or exceed the level you specify here.
      **log_file_dir:** in case you wish to log elsewhere. dk y tho.

    **->** a logger instance that you can use with logger.info(), etc.
    """

    if name is None:
        name = DEFAULT_LOGGER_NAME
    if console_level is None:
        console_level = DEFAULT_CONSOLE_LEVEL
    if file_level is None:
        file_level = DEFAULT_FILE_LEVEL
    if log_file_dir is None:
        log_file_dir = DEFAULT_LOG_DIRECTORY

    logger = getLogger(name)
    assert isinstance(logger, Lumberjack)
    logger.setup(console_level, file_level, log_file_dir)

    return logger

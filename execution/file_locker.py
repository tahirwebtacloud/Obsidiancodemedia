import os
import time

class FileLock:
    """
    A simple cross-platform file locker using atomic os.open(O_CREAT | O_EXCL).
    """
    def __init__(self, file_path, timeout=10, delay=0.05):
        self.lockfile = file_path + ".lock"
        self.timeout = timeout
        self.delay = delay
        self.fd = None

    def acquire(self):
        start_time = time.time()
        while True:
            try:
                # Exclusive creation: fails if file exists
                self.fd = os.open(self.lockfile, os.O_CREAT | os.O_EXCL | os.O_RDWR)
                return True
            except FileExistsError:
                if time.time() - start_time >= self.timeout:
                    raise TimeoutError(f"Timeout acquiring lock for {self.lockfile}")
                time.sleep(self.delay)
            except OSError as e:
                import errno
                if getattr(e, 'errno', None) == errno.EEXIST:
                    if time.time() - start_time >= self.timeout:
                        raise TimeoutError(f"Timeout acquiring lock for {self.lockfile}")
                    time.sleep(self.delay)
                else:
                    raise

    def release(self):
        if self.fd is not None:
            try:
                os.close(self.fd)
            except OSError:
                pass
            self.fd = None
            try:
                os.remove(self.lockfile)
            except OSError:
                pass

    def __enter__(self):
        self.acquire()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.release()

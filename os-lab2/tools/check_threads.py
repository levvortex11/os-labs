import subprocess
import time

p = subprocess.Popen(['./merge', '--threads', '4', '--size', '10000', '--hold', '3', '--quiet'], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
time.sleep(1)
subprocess.run(['ps', '-T', '-p', str(p.pid)], check=True)
p.wait()

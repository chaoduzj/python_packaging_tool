import subprocess
import sys

cmd = [sys.executable, "-c", "import sys; print(repr(sys.argv[1:]))", "--company-name=中文测试公司"]
print("cmd:", cmd)

result = subprocess.run(cmd, capture_output=True, text=True, encoding="gbk", errors="replace")
print("stdout:", repr(result.stdout))
print("stderr:", repr(result.stderr))
print("returncode:", result.returncode)

import subprocess
cmd = 'Get-CimInstance -ClassName Win32_Process -Filter "Name = \'python.exe\'" | Select-Object ProcessId, CommandLine | Format-List'
res = subprocess.run(['powershell', '-NoProfile', '-Command', cmd], capture_output=True, text=True)
print(res.stdout)

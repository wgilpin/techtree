"""
This script kills all running Python processes.
"""

# import os module
import os

# delete given process
os.system('wmic process where name="python.exe" delete')

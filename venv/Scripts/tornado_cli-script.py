#!E:\pycharm\pythons\Scripts\widget\dailyfresh\venv\Scripts\python.exe
# EASY-INSTALL-ENTRY-SCRIPT: 'tornado-cli==0.1','console_scripts','tornado_cli'
__requires__ = 'tornado-cli==0.1'
import re
import sys
from pkg_resources import load_entry_point

if __name__ == '__main__':
    sys.argv[0] = re.sub(r'(-script\.pyw?|\.exe)?$', '', sys.argv[0])
    sys.exit(
        load_entry_point('tornado-cli==0.1', 'console_scripts', 'tornado_cli')()
    )

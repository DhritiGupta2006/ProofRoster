import subprocess
import sys
import zipfile
from pathlib import Path
import shutil

ROOT=Path(__file__).resolve().parents[1]
def main():
    target=ROOT/'build'/'lambda-package'; target.mkdir(parents=True,exist_ok=True)
    subprocess.run([sys.executable,'-m','pip','install','--platform','manylinux2014_x86_64','--python-version','3.12','--implementation','cp','--only-binary=:all:','--no-compile','--target',str(target),'z3-solver==4.15.4.0'],check=True)
    shutil.copytree(ROOT/'lambda_solver',target/'lambda_solver',dirs_exist_ok=True,ignore=shutil.ignore_patterns('__pycache__'))
    archive=ROOT/'build'/'proofroster-lambda.zip'
    with zipfile.ZipFile(archive,'w',zipfile.ZIP_DEFLATED) as z:
        for file in target.rglob('*'):
            if file.is_file() and '__pycache__' not in file.parts: z.write(file,file.relative_to(target).as_posix())
    print(str(archive),archive.stat().st_size)

if __name__=='__main__': main()

"""Package portable source and evidence, without build caches or credentials."""
import zipfile
from agent.aws_clients import ROOT

def main():
    target=ROOT.parent/'ProofRoster-source.zip'
    excluded={'build','.venv','__pycache__','.pytest_cache','.git'}
    with zipfile.ZipFile(target,'w',zipfile.ZIP_DEFLATED) as archive:
        for path in ROOT.rglob('*'):
            relative=path.relative_to(ROOT)
            if not path.is_file() or excluded.intersection(relative.parts): continue
            if path.name=='.env' or path.suffix in ('.pyc','.zip'): continue
            archive.write(path,('ProofRoster'/relative).as_posix())
    print(target, target.stat().st_size)

if __name__=='__main__':main()

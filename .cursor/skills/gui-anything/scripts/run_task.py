"""Use the shared authenticated Run protocol from a copied Skill."""
import sys
from fast_map import find_home

def main():
    home=find_home()
    sys.path.insert(0,str(home/"backend" if (home/"backend/app").is_dir() else home))
    from app.workbench_cli import main as run_main
    return run_main(sys.argv[1:])

if __name__=="__main__": raise SystemExit(main())

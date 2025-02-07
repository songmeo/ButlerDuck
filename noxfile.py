import shutil
from pathlib import Path

import nox

BYPRODUCTS = [".coverage*", "*.log"]


# nox -s clean
@nox.session(python=False)
def clean(session: nox.Session) -> None:
    for w in BYPRODUCTS:
        for f in Path.cwd().glob(w):
            try:
                session.log(f"Removing: {f}")
                if f.is_dir():
                    shutil.rmtree(f, ignore_errors=True)
                else:
                    f.unlink(missing_ok=True)
            except Exception as ex:
                session.error(f"Failed to remove {f}: {ex}")


# nox -s mypy
@nox.session(reuse_venv=True)
def mypy(session: nox.Session) -> None:
    session.install("-e", ".")
    session.install("mypy ~= 1.14", "types-requests")
    session.run("mypy", "src/")


# nox -s black
@nox.session(reuse_venv=True)
def black(session: nox.Session) -> None:
    session.install("black ~= 24.10")
    session.run("black", "--check", ".")


# nox -s tests
# TODO: write tests
@nox.session(reuse_venv=True, default=False)
def test(session: nox.Session) -> None:
    session.install("-e", ".")
    session.install("coverage ~= 7.6")

    # Run pytest with coverage
    session.install("pytest ~= 8.3")
    session.install("pytest-asyncio ~= 0.23")
    session.run("coverage", "run", "-m", "pytest")

    # Generate coverage report
    session.run("coverage", "combine")
    session.run("coverage", "report", "--fail-under=25")
    if session.interactive:
        session.run("coverage", "html")
        report_file = Path.cwd().resolve() / "htmlcov" / "index.html"
        session.log(f"OPEN IN WEB BROWSER: file://{report_file}")


# nox -s build_run
@nox.session(reuse_venv=True, default=False)
def build_run(session: nox.Session) -> None:
    session.run("docker-compose", "up", "--build", external=True)

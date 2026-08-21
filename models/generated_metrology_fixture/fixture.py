"""STEP-first backend for the selected canonical mechanism program."""

from pathlib import Path

from mechanogenesis_engine.cad_backend import compile_assembly
from mechanogenesis_engine.compiler import load_program


PROGRAM_PATH = Path(__file__).with_name("program.json")


def gen_step():
    program = load_program(PROGRAM_PATH)
    return compile_assembly(program, "metrology_fixture")

from .agent import Agent

from tools.mathematics import (
    calculate,
    derivative,
    nth_derivative,
    integral,
    definite_integral,
    limit,
    series,
    solve_equation,
    solve_system,
    factor,
    expand,
    simplify,
    numerical,
    matrix_determinant,
    matrix_inverse,
    matrix_rank,
)

from tools.python_tool import run_python
from faculties.data_science import register_data_science


def create_agent():

    agent = Agent()

    # ========================================================
    # MATHEMATICS
    # ========================================================

    agent.register_tool(
        "calculate",
        "Evaluate a mathematical expression using SymPy.",
        calculate
    )

    agent.register_tool(
        "derivative",
        "Calculate the derivative of an expression.",
        derivative
    )

    agent.register_tool(
        "nth_derivative",
        "Calculate the nth derivative of an expression.",
        nth_derivative
    )

    agent.register_tool(
        "integral",
        "Calculate an indefinite integral.",
        integral
    )

    agent.register_tool(
        "definite_integral",
        "Calculate a definite integral.",
        definite_integral
    )

    agent.register_tool(
        "limit",
        "Calculate a mathematical limit.",
        limit
    )

    agent.register_tool(
        "series",
        "Calculate a Taylor or Maclaurin series.",
        series
    )

    agent.register_tool(
        "solve_equation",
        "Solve an algebraic equation.",
        solve_equation
    )

    agent.register_tool(
        "solve_system",
        "Solve simultaneous equations.",
        solve_system
    )

    agent.register_tool(
        "factor",
        "Factor an algebraic expression.",
        factor
    )

    agent.register_tool(
        "expand",
        "Expand an algebraic expression.",
        expand
    )

    agent.register_tool(
        "simplify",
        "Simplify an algebraic expression.",
        simplify
    )

    agent.register_tool(
        "numerical",
        "Calculate a numerical approximation.",
        numerical
    )

    agent.register_tool(
        "matrix_determinant",
        "Calculate the determinant of a matrix.",
        matrix_determinant
    )

    agent.register_tool(
        "matrix_inverse",
        "Calculate the inverse of a matrix.",
        matrix_inverse
    )

    agent.register_tool(
        "matrix_rank",
        "Calculate the rank of a matrix.",
        matrix_rank
    )

    # ========================================================
    # PYTHON / DATA SCIENCE
    # ========================================================

    agent.register_tool(
        "run_python",
        "Execute Python code for scientific computing, NumPy, "
        "Pandas, SymPy, statistics and data analysis.",
        run_python
    )

    # ========================================================
    # DATA SCIENCE FACULTY
    # ========================================================

    register_data_science(agent)

    return agent


def main():

    agent = create_agent()

    print("JARVIS ONLINE")
    print("Type 'exit' to quit.")

    while True:

        try:
            user_input = input("\nYou: ").strip()

        except KeyboardInterrupt:
            print("\nJARVIS: Goodbye.")
            break

        except EOFError:
            print("\nJARVIS: Goodbye.")
            break

        if user_input.lower() in {
            "exit",
            "quit",
            "goodbye"
        }:
            print("JARVIS: Goodbye.")
            break

        if not user_input:
            continue

        try:
            result = agent.run(user_input)

            print("JARVIS:", result)

        except Exception as e:

            print(
                "JARVIS: An error occurred:",
                e
            )


if __name__ == "__main__":
    main()
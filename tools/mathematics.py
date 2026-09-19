import sympy as sp
from sympy.parsing.sympy_parser import (
    parse_expr,
    standard_transformations,
    convert_xor,
    implicit_multiplication_application,
)

TRANSFORMATIONS = standard_transformations + (
    convert_xor,
    implicit_multiplication_application,
)

LOCALS = {
    "sin": sp.sin,
    "cos": sp.cos,
    "tan": sp.tan,
    "asin": sp.asin,
    "acos": sp.acos,
    "atan": sp.atan,
    "sinh": sp.sinh,
    "cosh": sp.cosh,
    "tanh": sp.tanh,
    "sqrt": sp.sqrt,
    "exp": sp.exp,
    "log": sp.log,
    "ln": sp.log,
    "Abs": sp.Abs,
    "abs": sp.Abs,
    "pi": sp.pi,
    "E": sp.E,
    "oo": sp.oo,
}


def _parse(expression):
    if not isinstance(expression, str):
        raise TypeError("Expression must be a string.")

    expression = expression.strip()

    if not expression:
        raise ValueError("No expression provided.")

    return parse_expr(
        expression,
        local_dict=LOCALS,
        transformations=TRANSFORMATIONS,
        evaluate=True,
    )


def calculate(expression):
    return str(sp.simplify(_parse(expression)))


def derivative(expression, variable="x"):
    return str(sp.simplify(
        sp.diff(_parse(expression), sp.Symbol(variable))
    ))


def nth_derivative(expression, variable="x", order=1):
    if order < 1:
        raise ValueError("Order must be >= 1.")

    return str(sp.simplify(
        sp.diff(_parse(expression), sp.Symbol(variable), order)
    ))


def integral(expression, variable="x"):
    return str(sp.integrate(
        _parse(expression),
        sp.Symbol(variable)
    ))


def definite_integral(expression, variable="x", lower=0, upper=1):
    x = sp.Symbol(variable)

    return str(sp.simplify(
        sp.integrate(
            _parse(expression),
            (x, _parse(str(lower)), _parse(str(upper)))
        )
    ))


def limit(expression, variable="x", point=0, direction="+-"):
    x = sp.Symbol(variable)

    return str(
        sp.limit(
            _parse(expression),
            x,
            _parse(str(point)),
            dir=direction,
        )
    )


def series(expression, variable="x", point=0, order=6):
    if order < 1:
        raise ValueError("Order must be >= 1.")

    x = sp.Symbol(variable)

    return str(
        sp.series(
            _parse(expression),
            x,
            _parse(str(point)),
            order,
        )
    )


def solve_equation(expression, variable="x"):
    x = sp.Symbol(variable)

    if "=" in expression:
        left, right = expression.split("=", 1)

        equation = sp.Eq(
            _parse(left),
            _parse(right)
        )
    else:
        equation = _parse(expression)

    return [str(v) for v in sp.solve(equation, x)]


def solve_system(equations, variables):
    symbols = sp.symbols(" ".join(variables))

    parsed = []

    for equation in equations:
        if "=" in equation:
            left, right = equation.split("=", 1)

            parsed.append(
                sp.Eq(
                    _parse(left),
                    _parse(right)
                )
            )
        else:
            parsed.append(_parse(equation))

    result = sp.solve(
        parsed,
        symbols,
        dict=True
    )

    return [
        {str(k): str(v) for k, v in solution.items()}
        for solution in result
    ]


def factor(expression):
    return str(sp.factor(_parse(expression)))


def expand(expression):
    return str(sp.expand(_parse(expression)))


def simplify(expression):
    return str(sp.simplify(_parse(expression)))


def matrix_determinant(matrix):
    return str(sp.Matrix(matrix).det())


def matrix_inverse(matrix):
    M = sp.Matrix(matrix)

    if M.det() == 0:
        raise ValueError("Matrix is singular.")

    return str(M.inv())


def matrix_rank(matrix):
    return str(sp.Matrix(matrix).rank())


def numerical(expression, digits=10):
    return str(sp.N(_parse(expression), digits))
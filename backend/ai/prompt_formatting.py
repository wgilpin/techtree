"""Module containing standard prompt formatting instructions."""

LATEX_FORMATTING_INSTRUCTIONS = r"""
If the response contains mathematical formulas or equations, use basic latex syntax, enclosed in $ delimiters if inline
or in $$ delimeters if not inline. For example:

"Consider the Newtonian formula for escape velocity: v_esc = sqrt(2GM/R).
Imagine applying this purely Newtonian formula to a hypothetical object"

This should be formatted as:

"Consider the Newtonian formula for escape velocity: $v_{esc} = \sqrt{2GM\over{R}}$.
Imagine applying this purely Newtonian formula to a hypothetical object"
"""
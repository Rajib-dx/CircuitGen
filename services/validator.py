# services/validator.py
import schemdraw
import schemdraw.elements as elm

def validate_and_draw(code: str) -> tuple[bool, str]:
    """
    Executes LLM-generated Schemdraw code and extracts the SVG string.
    """
    if not isinstance(code, str) or not code.strip():
        return False, "No schematic code provided."

    # Isolate execution environment with access to schemdraw elements
    local_scope = {"schemdraw": schemdraw, "elm": elm}
    
    try:
        # The LLM is instructed to assign the schematic to a variable named 'd'
        exec(code, globals(), local_scope)
        
        drawing = local_scope.get("d")
        if not drawing or not isinstance(drawing, schemdraw.Drawing):
            return False, "The code did not produce a valid schemdraw.Drawing object named 'd'."
        
        # Extract the SVG raw string
        svg_bytes = drawing.get_imagedata('svg')
        svg_string = svg_bytes.decode('utf-8')
        
        return True, svg_string

    except Exception as error:
        # If the LLM wires something illegally, Schemdraw catches it here
        return False, f"Drawing execution failed: {str(error)}"
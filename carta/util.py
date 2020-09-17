# TODO split into files

logger = logging.getLogger("carta_scripting")
logger.setLevel(logging.ERROR)
logger.addHandler(logging.StreamHandler())


class CartaScriptingException(Exception):
    pass


class Macro:
    def __init__(self, target, variable):
        self.target = target
        self.variable = variable
        
    def __repr__(self):
        return f"Macro('{self.target}', '{self.variable}')"


class CartaEncoder(json.JSONEncoder):
    def default(self, obj):
        if isinstance(obj, Macro):
            return {"macroTarget" : obj.target, "macroVariable" : obj.variable}
        if type(obj).__module__ == "numpy" and type(obj).__name__ == "ndarray":
            # The condition is a workaround to avoid importing numpy
            return obj.tolist()
        return json.JSONEncoder.default(self, obj)

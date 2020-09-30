import re
import functools
import inspect

from .util import CartaValidationException

class Parameter:
    description="UNKNOWN"
    
    def validate(self, value):
        raise NotImplementedError

class String(Parameter):
    description = "a string"
    
    def __init__(self, regex=None, ignorecase=False):
        self.regex = regex
        self.flags = re.IGNORECASE if ignorecase else 0
        
    def validate(self, value):
        if not isinstance(value, str):
            raise TypeError(f"{value} has type {type(value)} but a string was expected.")
        
        if self.regex is not None and not re.search(self.regex, value, self.flags):
            raise ValueError(f"{value} does not match {self.regex}")

class Number(Parameter):
    description = "a number"
    
    def __init__(self, min=None, max=None):
        self.min = min
        self.max = max
        
    def validate(self, value):
        # We do this instead of explicitly checking for an integer or a float
        # so that we can include numpy types without a dependency on numpy
        try:
            float(value)
        except TypeError:
            raise TypeError(f"{value} has type {type(value)} but a number was expected.")
        
        if self.min is not None and value < self.min:
            raise ValueError(f"{value} is smaller than minimum value {self.min}.")
        
        if self.max is not None and value > self.max:
            raise ValueError(f"{value} is larger than maximum value {self.max}.")
        
class Boolean(Parameter):
    description = "a boolean"
    
    def validate(self, value):
        if value not in (0, 1):
            raise TypeError(f"{value} is not a boolean value.")
        

class NoneParameter(Parameter):
    description = "None"
    
    def validate(self, value):
        if value is not None:
            raise ValueError(f"{value} is not None.")


class OneOf(Parameter):
    def __init__(self, *options, normalize=None):
        self.options = options
        self.normalize = normalize
        self.description = f"one of {self.options}"
        
    def validate(self, value):
        if self.normalize is not None:
            value = self.normalize(value)
        
        if value not in self.options:
            raise ValueError(f"{value} is not {self.description}")


class Union(Parameter):
    def __init__(self, options, description=None):
        self.options = options
        self.description = description or " or ".join(o.description for o in options)
        
    def validate(self, value):
        valid = False
        
        for option in self.options:
            try:
                option.validate(value)
            except:
                pass
            else:
                valid = True
                break
        
        if not valid:
            raise ValueError(f"{value} is not {self.description}.")


class Constant(OneOf):
    def __init__(self, clazz):
        options = set(v for k, v in inspect.getmembers(clazz, lambda x:not(inspect.isroutine(x))) if not k.startswith("__"))
        super().__init__(*options)
        self.description = f"a constant property of class {clazz.__name__}"
        

class NoneOr(Union):
    def __init__(self, param):
        options = (
            param,
            NoneParameter(),
        )
        super().__init__(options)


class IterableOf(Parameter):
    def __init__(self, param):
        self.param = param
        self.description = f"an iterable of {self.param.description}"
    
    def validate(self, value):
        for v in value:
            self.param.validate(v)
            

COLORNAMES = ('aliceblue', 'antiquewhite', 'aqua', 'aquamarine', 'azure', 'beige', 'bisque', 'black', 'blanchedalmond', 'blue', 'blueviolet', 'brown', 'burlywood', 'cadetblue', 'chartreuse', 'chocolate', 'coral', 'cornflowerblue', 'cornsilk', 'crimson', 'cyan', 'darkblue', 'darkcyan', 'darkgoldenrod', 'darkgray', 'darkgrey', 'darkgreen', 'darkkhaki', 'darkmagenta', 'darkolivegreen', 'darkorange', 'darkorchid', 'darkred', 'darksalmon', 'darkseagreen', 'darkslateblue', 'darkslategray', 'darkslategrey', 'darkturquoise', 'darkviolet', 'deeppink', 'deepskyblue', 'dimgray', 'dimgrey', 'dodgerblue', 'firebrick', 'floralwhite', 'forestgreen', 'fuchsia', 'gainsboro', 'ghostwhite', 'gold', 'goldenrod', 'gray', 'grey', 'green', 'greenyellow', 'honeydew', 'hotpink', 'indianred', 'indigo', 'ivory', 'khaki', 'lavender', 'lavenderblush', 'lawngreen', 'lemonchiffon', 'lightblue', 'lightcoral', 'lightcyan', 'lightgoldenrodyellow', 'lightgray', 'lightgrey', 'lightgreen', 'lightpink', 'lightsalmon', 'lightseagreen', 'lightskyblue', 'lightslategray', 'lightslategrey', 'lightsteelblue', 'lightyellow', 'lime', 'limegreen', 'linen', 'magenta', 'maroon', 'mediumaquamarine', 'mediumblue', 'mediumorchid', 'mediumpurple', 'mediumseagreen', 'mediumslateblue', 'mediumspringgreen', 'mediumturquoise', 'mediumvioletred', 'midnightblue', 'mintcream', 'mistyrose', 'moccasin', 'navajowhite', 'navy', 'oldlace', 'olive', 'olivedrab', 'orange', 'orangered', 'orchid', 'palegoldenrod', 'palegreen', 'paleturquoise', 'palevioletred', 'papayawhip', 'peachpuff', 'peru', 'pink', 'plum', 'powderblue', 'purple', 'red', 'rosybrown', 'royalblue', 'saddlebrown', 'salmon', 'sandybrown', 'seagreen', 'seashell', 'sienna', 'silver', 'skyblue', 'slateblue', 'slategray', 'slategrey', 'snow', 'springgreen', 'steelblue', 'tan', 'teal', 'thistle', 'tomato', 'turquoise', 'violet', 'wheat', 'white', 'whitesmoke', 'yellow', 'yellowgreen')


class TupleColor(Parameter):
    description = "an HTML color tuple"
    
    def _assert_length(self, params, number):
        if len(params) != number:
            raise ValueError(f"expected {number} parameters but got {len(params)}.")
        
    def _assert_percentage(self, param):
        if not param.endswith("%") or not 0 <= float(param[:-1]) <= 100:
            raise ValueError(f"{param} is not a valid percentage.")
        
    def _assert_between(self, param, min, max):
        if not min <= float(param) <= max:
            raise ValueError(f"{param} is not a number between {min} and {max}.")
    
    def _validate_rgb(self, params):
        self._assert_length(params, 3)
                
        try:
            for p in params:
                self._assert_percentage(p)
        except:
            try:
                for p in params:
                    self._assert_between(p, 0, 255)
            except:
                raise ValueError("parameters must either all be percentages or all be numbers between 0 and 255.")
    
    def _validate_rgba(self, params):
        self._assert_length(params, 4)
        self._validate_rgb(params[:3])
        self._assert_between(params[3], 0, 1)
    
    def _validate_hsl(self, params):
        self._assert_length(params, 3)
        self._assert_between(params[0], 0, 360)
        self._assert_percentage(params[1])
        self._assert_percentage(params[2])
    
    def _validate_hsla(self, params):
        self._assert_length(params, 4)
        self._validate_hsl(params[:3])
        self._assert_between(params[3], 0, 1)
    
    def validate(self, value):
        value = re.sub('\s', '', value)
        
        m = re.match('(hsla?|rgba?)\((.*)\)', value)
        if m is None:
            raise ValueError(f"{value} is not {self.description}.")
        
        func, params = m.groups()
        try:
            getattr(self, f"_validate_{func}")(params.split(","))
        except (TypeError, ValueError) as e:
            raise ValueError(f"{value} is not a valid {func.upper()} color tuple: {e}")
        

class Color(Union):
    def __init__(self):
        options = (
            OneOf(*COLORNAMES, lambda v: v.lower()), # Named color
            String("#[0-9a-f]{6}", re.IGNORECASE), # 6-digit hex
            String("#[0-9a-f]{3}", re.IGNORECASE), # 3-digit hex
            TupleColor(), # RGB, RGBA, HSL, HSLA
        )
        super().__init__(options, "an HTML color specification")

# We're assuming that this decorator will only be used for methods; we're skipping the first parameter
def validate(*vargs):
    def decorator(func):
        @functools.wraps(func)
        def newfunc(self, *args):
            try:
                for param, value in zip(vargs, args):
                    param.validate(value)
            except (TypeError, ValueError) as e:
                raise CartaValidationException(f"Invalid function parameter: {e}")
            return func(self, *args)
        return newfunc
    return decorator

import re
import functools

class Parameter:
    def _assert_length(self, params, number):
        if len(params) != number:
            raise ValueError(f"expected {number} parameters but got {len(params)}.")
        
    def _assert_percentage(self, param):
        if not param.endswith("%") or not 0 <= float(param[:-1]) <= 100:
            raise ValueError(f"{param} is not a valid percentage.")
        
    def _assert_between(self, param, min, max):
        if not min <= float(param) <= max:
            raise ValueError(f"{param} is not a number between {min} and {max}.")
    
    def validate(self, value):
        raise NotImplementedError

class String(Parameter):
    def __init__(regex=None, ignorecase=False):
        self.regex = regex
        self.flags = re.IGNORECASE if ignorecase else 0
        
    def validate(self, value):
        if not isinstance(value, str):
            raise TypeError(f"{value} has type {type(value)} but a string was expected.")
        
        if regex is not None and not re.search(self.regex, value, self.flags):
            raise ValueError(f"{value} does not match {self.regex}")

class Number(Parameter):
    def __init__(min=None, max=None):
        self.min = min
        self.max = max
        
    def validate(self, value):
        if not isinstance(value, (int, float)):
            raise TypeError(f"{value} has type {type(value)} but a number was expected.")
        
        if self.min is not None and value < self.min:
            raise ValueError(f"{value} is smaller than minimum value {self.min}.")
        
        if self.max is not None and value > self.max:
            raise ValueError(f"{value} is larger than maximum value {self.max}.")
        
class Boolean(Parameter):
    def validate(self, value):
        if value not in (0, 1):
            raise TypeError(f"{value} is not a boolean value.")

class OneOf(Parameter):
    def __init__(self, options, normalize=None):
        self.options = options
        self.normalize = normalize
        
    def validate(self, value):
        if self.normalize is not None:
            value = self.normalize(value)
        
        if value not in self.options:
            raise ValueError(f"{value} is not one of: {self.options}")
        
class Union(Parameter):
    def __init__(self, options, description):
        self.options = options
        
    def validate(value):
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
            raise ValueError("{value} is not a valid {self.description}.")


COLORNAMES = ('aliceblue', 'antiquewhite', 'aqua', 'aquamarine', 'azure', 'beige', 'bisque', 'black', 'blanchedalmond', 'blue', 'blueviolet', 'brown', 'burlywood', 'cadetblue', 'chartreuse', 'chocolate', 'coral', 'cornflowerblue', 'cornsilk', 'crimson', 'cyan', 'darkblue', 'darkcyan', 'darkgoldenrod', 'darkgray', 'darkgrey', 'darkgreen', 'darkkhaki', 'darkmagenta', 'darkolivegreen', 'darkorange', 'darkorchid', 'darkred', 'darksalmon', 'darkseagreen', 'darkslateblue', 'darkslategray', 'darkslategrey', 'darkturquoise', 'darkviolet', 'deeppink', 'deepskyblue', 'dimgray', 'dimgrey', 'dodgerblue', 'firebrick', 'floralwhite', 'forestgreen', 'fuchsia', 'gainsboro', 'ghostwhite', 'gold', 'goldenrod', 'gray', 'grey', 'green', 'greenyellow', 'honeydew', 'hotpink', 'indianred', 'indigo', 'ivory', 'khaki', 'lavender', 'lavenderblush', 'lawngreen', 'lemonchiffon', 'lightblue', 'lightcoral', 'lightcyan', 'lightgoldenrodyellow', 'lightgray', 'lightgrey', 'lightgreen', 'lightpink', 'lightsalmon', 'lightseagreen', 'lightskyblue', 'lightslategray', 'lightslategrey', 'lightsteelblue', 'lightyellow', 'lime', 'limegreen', 'linen', 'magenta', 'maroon', 'mediumaquamarine', 'mediumblue', 'mediumorchid', 'mediumpurple', 'mediumseagreen', 'mediumslateblue', 'mediumspringgreen', 'mediumturquoise', 'mediumvioletred', 'midnightblue', 'mintcream', 'mistyrose', 'moccasin', 'navajowhite', 'navy', 'oldlace', 'olive', 'olivedrab', 'orange', 'orangered', 'orchid', 'palegoldenrod', 'palegreen', 'paleturquoise', 'palevioletred', 'papayawhip', 'peachpuff', 'peru', 'pink', 'plum', 'powderblue', 'purple', 'red', 'rosybrown', 'royalblue', 'saddlebrown', 'salmon', 'sandybrown', 'seagreen', 'seashell', 'sienna', 'silver', 'skyblue', 'slateblue', 'slategray', 'slategrey', 'snow', 'springgreen', 'steelblue', 'tan', 'teal', 'thistle', 'tomato', 'turquoise', 'violet', 'wheat', 'white', 'whitesmoke', 'yellow', 'yellowgreen')


class TupleColor(Parameter):    
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
            raise ValueError(f"{value} is not a recognised HTML color tuple.")
        
        func, params = m.groups()
        try:
            getattr(self, f"_validate_{func}")(params.split(","))
        except (TypeError, ValueError) as e:
            raise ValueError(f"{value} is not a valid {func.upper()} color tuple: {e}")
        

class Color(Union):
    def __init__(self):
        options = (
            OneOf(COLORNAMES, lambda v: v.lower()), # Named color
            String("#[0-9a-f]{6}", re.IGNORECASE), # 6-digit hex
            String("#[0-9a-f]{3}", re.IGNORECASE), # 3-digit hex
            TupleColor(), # RGB, RGBA, HSL, HSLA
        )
        super().__init__(options, "HTML color specification")


class Enum(Parameter):
    def __init__(self, clazz):
        self.clazz = clazz
        
    def validate(self, value):
        properties = set(v for k, v in self.clazz.__dict__.items() if not k.startswith("__"))
        if not value in properties:
            raise ValueError(f"{value} is not a property of class {self.clazz.__name__}")


def validate(*vargs):
    def decorator(func):
        @functools.wraps(func)
        def newfunc(*args):
            for param, value in zip(vargs, args):
                param.validate(value)
            func(*args)
        return newfunc
    return decorator

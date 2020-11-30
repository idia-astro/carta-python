"""This module provides a collection of descriptors of the permitted types and values of parameters passed to :obj:`carta.client.Session` and :obj:`carta.client.Image` methods. They are associated with methods through a decorator which performs the validation at runtime and also injects parameter descriptions into the methods' docstrings."""

import re
import functools
import inspect

from .util import CartaValidationFailed

class Parameter:
    """The top-level class for parameter validation."""
    
    def validate(self, value, parent):
        """Validate the value provided.
        
        Parameters
        ----------
        value
            The value to be validated.
        parent
            The object which owns the decorated method.
        
        Raises
        ------
        TypeError
            If the value provided is not of the correct type.
        ValueError
            If the value provided is of the correct type but has an invalid value.
        AttributeError
            If the check depends on an attribute on the parent object of the decorated method, and it does not exist.
        """
        raise NotImplementedError
    
    @property
    def description(self):
        """A human-readable description of this parameter descriptor."""
        return "UNKNOWN"

class String(Parameter):
    """A string parameter.
    
    Parameters
    ----------
    regex : str, optional
        A regular expression string which the parameter must match.
    ignorecase : bool, optional
        Whether the regular expression match should be case-insensitive.
        
    Attributes
    ----------
    regex : str
        A regular expression string which the parameter must match.
    flags : int
        The flags to use when matching the regular expression. This is set to :obj:`re.IGNORECASE` or zero.
    """
    
    def __init__(self, regex=None, ignorecase=False):
        self.regex = regex
        self.flags = re.IGNORECASE if ignorecase else 0
        
    def validate(self, value, parent):
        """Check if the value is a string and if it matches a regex if one was provided.
        
        See :obj:`carta.validation.Parameter.validate` for general information about this method.
        """
        if not isinstance(value, str):
            raise TypeError(f"{value} has type {type(value)} but a string was expected.")
        
        if self.regex is not None and not re.search(self.regex, value, self.flags):
            raise ValueError(f"{value} does not match {self.regex}")
    
    @property
    def description(self):
        if self.regex:
            return f"`a string matching` ``{self.regex}``"
        return "a string"

class Number(Parameter):
    """An integer or floating point scalar numeric parameter. 
    
    Parameters
    ----------
    min : number, optional
        The lower bound.
    max : number, optional
        The upper bound.
    interval : int
        A bitmask which describes whether the bounds are included or excluded. The constant attributes defined on this class should be used. By default both bounds are included.
        
    Attributes
    ----------
    min : number
        The lower bound.
    max : number
        The upper bound.
    min_included : bool
        Whether the lower bound is included.
    max_included : bool
        Whether the upper bound is included.
    """
    
    EXCLUDE, INCLUDE_MIN, INCLUDE_MAX, INCLUDE = range(4)
    
    def __init__(self, min=None, max=None, interval=INCLUDE):
        self.min = min
        self.max = max
        self.min_included = bool(interval & self.INCLUDE_MIN)
        self.max_included = bool(interval & self.INCLUDE_MAX)
        
    def validate(self, value, parent):
        """Check if the value is a number and falls within any bounds that were provided.
        
        We check the type by attempting to convert the value to `float`. We do this instead of comparing types directly to support compatible numeric types from e.g. the numpy library without having to anticipate and check for them explicitly and without introducing import dependencies.
                
        See :obj:`carta.validation.Parameter.validate` for general information about this method.
        """
        try:
            float(value)
        except TypeError:
            raise TypeError(f"{value} has type {type(value)} but a number was expected.")
        
        if self.min is not None:
            if self.min_included:
                if value < self.min:
                    raise ValueError(f"{value} is smaller than minimum value {self.min}.")
            else:
                if value <= self.min:
                    raise ValueError(f"{value} is smaller than or equal to minimum value {self.min}.")
        
        if self.max is not None:
            if self.max_included:
                if value > self.max:
                    raise ValueError(f"{value} is greater than maximum value {self.max}.")
            else:
                if value >= self.max:
                    raise ValueError(f"{value} is greater than or equal to maximum value {self.max}.")
    
    @property
    def description(self):
        desc = ["a number"]
        
        if self.min is not None:
            desc.append(f"greater than{' or equal to' if self.min_included else ''} {self.min}")
            
            if self.max is not None:
                desc.append("and")
        
        if self.max is not None:
            desc.append(f"smaller than{' or equal to' if self.max_included else ''} {self.max}")
        
        return " ".join(desc)
        
        
class Boolean(Parameter):
    """A boolean parameter."""
    
    def validate(self, value, parent):
        """Check if the value is boolean. It may be expressed as a numeric 1 or 0 value. 
        
        See :obj:`carta.validation.Parameter.validate` for general information about this method.
        """
        if value not in (0, 1):
            raise TypeError(f"{value} is not a boolean value.")
        
    @property
    def description(self):
        return "a boolean"
        

class NoneParameter(Parameter):
    """A parameter which must be `None`. This is not intended to be used directly; it is used together with :obj:`carta.validation.Union` for optional parameters with a default value of `None`."""
    
    def validate(self, value, parent):
        """Check if the value is `None`. 
        
        See :obj:`carta.validation.Parameter.validate` for general information about this method.
        """
        if value is not None:
            raise ValueError(f"{value} is not None.")
        
    @property
    def description(self):
        return "None"


class OneOf(Parameter):
    """A parameter which must be one of several discrete values.
    
    Parameters
    ----------
    *options : iterable
        An iterable of permitted values.
    normalize : function, optional
        A function for applying a transformation to the value before the comparison: for example, `lambda x: x.lower()`.
        
    Attributes
    ----------
    options : iterable
        An iterable of permitted values.
    normalize : function, optional
        A function for applying a transformation to the value before the comparison.
    """
    def __init__(self, *options, normalize=None):
        self.options = options
        self.normalize = normalize
        
    def validate(self, value, parent):
        """Check if the value is equal to one of the provided options. If a normalization function is given, this is first used to transform the value. 
        
        See :obj:`carta.validation.Parameter.validate` for general information about this method.
        """
        if self.normalize is not None:
            value = self.normalize(value)
        
        if value not in self.options:
            raise ValueError(f"{value} is not {self.description}")
        
    @property
    def description(self):
        return f"one of {', '.join(str(o) for o in self.options)}"


class Union(Parameter):
    """A union of other parameter descriptors.
    
    Parameters
    ----------
    options : iterable of :obj:`carta.validation.Parameter` objects
        An iterable of valid descriptors for this parameter
    description : str, optional
        A custom description. The default is generated from the descriptions of the provided options.
        
    Attributes
    ----------
    options : iterable of :obj:`carta.validation.Parameter` objects
        An iterable of valid descriptors for this parameter.
    """
    def __init__(self, options, description=None):
        self.options = options
        self._description = description
        
    def validate(self, value, parent):
        """Check if the value can be validated with one of the provided descriptors. The descriptors are evaluated in the order that they are given, and the function exits after the first successful validation.
        
        See :obj:`carta.validation.Parameter.validate` for general information about this method.
        """
        valid = False
        
        for option in self.options:
            try:
                option.validate(value, parent)
            except:
                pass
            else:
                valid = True
                break
        
        if not valid:
            raise ValueError(f"{value} is not {self.description}.")
        
    @property
    def description(self):
        return self._description or " or ".join(o.description for o in self.options)


class Constant(OneOf):
    """A parameter which must match a class property on the provided class. Intended for use with the constants defined in :obj:`carta.constants`.
    
    Parameters
    ----------
    clazz : class
        The parameter must match one of the properties of this class.
    
    Attributes
    ----------
    options : iterable
        An iterable of the permitted options.
    clazz : class
        The parameter must match one of the properties of this class.
    """
    def __init__(self, clazz):
        options = set(v for k, v in inspect.getmembers(clazz, lambda x:not(inspect.isroutine(x))) if not k.startswith("__"))
        super().__init__(*options)
        self.clazz = clazz
        
    @property
    def description(self):
        if self.clazz.__module__ is None or self.clazz.__module__ == str.__class__.__module__:
            fullname = self.clazz.__name__  # Avoid reporting __builtin__
        else:
            fullname = self.clazz.__module__ + '.' + self.clazz.__name__
        return f"`a class property of` :obj:`{fullname}`"
        

class NoneOr(Union):
    """A parameter which can match the given descriptor or `None`. Used for optional parameters which are `None` by default.
    
    Parameters
    ----------
    param : :obj:`carta.validation.Parameter`
        The parameter descriptor.
    
    Attributes
    ----------
    param : :obj:`carta.validation.Parameter`
        The parameter descriptor.
    """
    def __init__(self, param):
        options = (
            param,
            NoneParameter(),
        )
        super().__init__(options)


class IterableOf(Parameter):
    """An iterable of values which must match the given descriptor.
    
    Parameters
    ----------
    param : :obj:`carta.validation.Parameter`
        The parameter descriptor.
    
    Attributes
    ----------
    param : :obj:`carta.validation.Parameter`
        The parameter descriptor.
    """
    def __init__(self, param):
        self.param = param
    
    def validate(self, value, parent):
        """Check if each element of the iterable can be validated with the given descriptor.
        
        See :obj:`carta.validation.Parameter.validate` for general information about this method.
        """
        for v in value:
            self.param.validate(v, parent)
        
    @property
    def description(self):
        return f"an iterable of {self.param.description}"
            

COLORNAMES = ('aliceblue', 'antiquewhite', 'aqua', 'aquamarine', 'azure', 'beige', 'bisque', 'black', 'blanchedalmond', 'blue', 'blueviolet', 'brown', 'burlywood', 'cadetblue', 'chartreuse', 'chocolate', 'coral', 'cornflowerblue', 'cornsilk', 'crimson', 'cyan', 'darkblue', 'darkcyan', 'darkgoldenrod', 'darkgray', 'darkgrey', 'darkgreen', 'darkkhaki', 'darkmagenta', 'darkolivegreen', 'darkorange', 'darkorchid', 'darkred', 'darksalmon', 'darkseagreen', 'darkslateblue', 'darkslategray', 'darkslategrey', 'darkturquoise', 'darkviolet', 'deeppink', 'deepskyblue', 'dimgray', 'dimgrey', 'dodgerblue', 'firebrick', 'floralwhite', 'forestgreen', 'fuchsia', 'gainsboro', 'ghostwhite', 'gold', 'goldenrod', 'gray', 'grey', 'green', 'greenyellow', 'honeydew', 'hotpink', 'indianred', 'indigo', 'ivory', 'khaki', 'lavender', 'lavenderblush', 'lawngreen', 'lemonchiffon', 'lightblue', 'lightcoral', 'lightcyan', 'lightgoldenrodyellow', 'lightgray', 'lightgrey', 'lightgreen', 'lightpink', 'lightsalmon', 'lightseagreen', 'lightskyblue', 'lightslategray', 'lightslategrey', 'lightsteelblue', 'lightyellow', 'lime', 'limegreen', 'linen', 'magenta', 'maroon', 'mediumaquamarine', 'mediumblue', 'mediumorchid', 'mediumpurple', 'mediumseagreen', 'mediumslateblue', 'mediumspringgreen', 'mediumturquoise', 'mediumvioletred', 'midnightblue', 'mintcream', 'mistyrose', 'moccasin', 'navajowhite', 'navy', 'oldlace', 'olive', 'olivedrab', 'orange', 'orangered', 'orchid', 'palegoldenrod', 'palegreen', 'paleturquoise', 'palevioletred', 'papayawhip', 'peachpuff', 'peru', 'pink', 'plum', 'powderblue', 'purple', 'red', 'rosybrown', 'royalblue', 'saddlebrown', 'salmon', 'sandybrown', 'seagreen', 'seashell', 'sienna', 'silver', 'skyblue', 'slateblue', 'slategray', 'slategrey', 'snow', 'springgreen', 'steelblue', 'tan', 'teal', 'thistle', 'tomato', 'turquoise', 'violet', 'wheat', 'white', 'whitesmoke', 'yellow', 'yellowgreen')


class TupleColor(Parameter):
    """An HTML color tuple. Not intended to be used directly; you probably want :obj:`carta.validation.Color` instead."""
    
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
    
    def validate(self, value, parent):
        """Check if the value can be parsed as a color tuple, and validate the tuple elements.
        
        See :obj:`carta.validation.Parameter.validate` for general information about this method.
        """
        value = re.sub('\s', '', value)
        
        m = re.match('(hsla?|rgba?)\((.*)\)', value)
        if m is None:
            raise ValueError(f"{value} is not {self.description}.")
        
        func, params = m.groups()
        try:
            getattr(self, f"_validate_{func}")(params.split(","))
        except (TypeError, ValueError) as e:
            raise ValueError(f"{value} is not a valid {func.upper()} color tuple: {e}")
        
    @property
    def description(self):
        return "an HTML color tuple"
        

class Color(Union):
    """Any valid HTML color specification: a 3- or 6-digit hex triplet, an RBG(A) or HSL(A) tuple, or one of the 147 named colors."""
    def __init__(self):
        options = (
            OneOf(*COLORNAMES, lambda v: v.lower()), # Named color
            String("#[0-9a-f]{6}", re.IGNORECASE), # 6-digit hex
            String("#[0-9a-f]{3}", re.IGNORECASE), # 3-digit hex
            TupleColor(), # RGB, RGBA, HSL, HSLA
        )
        super().__init__(options, "an HTML color specification")


class Attr(str):
    """A wrapper for arguments to be passed to the :obj:`carta.validation.Evaluate` descriptor. These arguments are string names of properties on the parent object of the decorated method, which will be evaluated at runtime."""
    pass


class Evaluate(Parameter):
    """A descriptor which is constructed at runtime using properties of the parent object of the decorated method.
    
    Parameters
    ----------
    paramclass : a :obj:`carta.validation.Parameter` class
        The class of the parameter descriptor to construct.
    *args : iterable
        Arguments to pass to the constructor; either literals or :obj:`carta.validation.Attr` objects which will be evaluated from properties on the parent object at runtime.
    
    Attributes
    ----------
    paramclass : a :obj:`carta.validation.Parameter` class
        The class of the parameter descriptor to construct.
    args : iterable
        Arguments to pass to the constructor.
    """
    
    def __init__(self, paramclass, *args):
        self.paramclass = paramclass
        self.args = args
        
    def validate(self, value, parent):
        args = list(self.args)
        for i, arg in enumerate(args):
            if isinstance(arg, Attr):
                args[i] = getattr(parent, arg)
                
        param = self.paramclass(*args)
        param.validate(value, parent)
        
    @property
    def description(self):
        args = list(self.args)
        for i, arg in enumerate(args):
            if isinstance(arg, Attr):
                args[i] = f"self.{arg}"
        
        # This is a bit magic, and relies on the lack of any kind of type checking in the constructors
        param = self.paramclass(*args)
        return f"{param.description}, evaluated at runtime"


def validate(*vargs):
    """The function which returns the decorator used to validate method parameters.
    
    It is assumed that the function to be decorated is an object method and the first parameter is `self`; this parameter is therefore ignored by the decorator. The remaining positional parameters are validated in order using the provided descriptors. The descriptors are also combined pairwise with the parameter names in the signature of the original function to create a dictionary for validating keyword parameters.
    
    Functions with `*args` or `**kwargs` are not currently supported: use iterables and explicit keyword parameters instead.
    
    The decorator inserts the descriptions of the parameters into the docstring of the decorated function, if placeholders have been left for them in the original docstring. The descriptions are passed as positional parameters to :obj:`str.format`.
    
    The `self` parameter is passed into the validation method of each descriptor, so that checks can depend on properties to be evaluated at runtime (this is currently used by :obj:`carta.validation.Evaluate`).

    The decorated function raises a :obj:`carta.util.CartaValidationFailed` if one of the parameters fails to validate.
    
    Parameters
    ----------
    *vargs : iterable of :obj:`carta.validation.Parameter` objects
        Descriptors to be used to validate the function parameters, in the same order as the parameters.
        
    Returns
    -------
    function
        The decorator function.
    """
        
    def decorator(func):
        kwvargs = {k:v for (k, v) in zip(inspect.getfullargspec(func).args, vargs)}
        
        @functools.wraps(func)
        def newfunc(self, *args, **kwargs):
            try:
                for param, value in zip(vargs, args):
                    param.validate(value, self)
                    
                for key, value in kwargs.items():
                    try:
                        param = kwvargs[key]
                        param.validate(value, self)
                    except KeyError:
                        raise CartaValidationFailed(f"Unexpected keyword parameter: {key}")
            except (TypeError, ValueError, AttributeError) as e:
                # Strip out any documentation formatting from the descriptions
                msg = str(e)
                msg = re.sub(":obj:`(.*)`", r"\1", msg)
                msg = re.sub("``(.*)``", r"\1", msg)
                raise CartaValidationFailed(f"Invalid function parameter: {msg}")
            return func(self, *args, **kwargs)
        
        if newfunc.__doc__ is not None:
            newfunc.__doc__ = newfunc.__doc__.format(*(p.description for p in vargs))
                    
        return newfunc
    return decorator

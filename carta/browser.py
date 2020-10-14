"""This module provides browser objects which can be used to create new sessions. It depends on the `selenium` library. The desired browser and its corresponding web driver also have to be installed."""

import re
import time

from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.desired_capabilities import DesiredCapabilities

from .util import CartaScriptingException
from .client import Session

class Browser:
    """The top-level browser class.
    
    Some common use cases are provided as subclasses, but you may instantiate this class directly to create a browser with custom configuration.
    
    Parameters
    ----------
    driver_class : a selenium web driver class
        The class to use for the browser driver.
    **kwargs
        Keyword arguments which will be passed to the driver class constructor.
        
    Attributes
    ----------
    driver : :obj:`selenium.webdriver.remote.webdriver.WebDriver`
        The browser driver.
    """
    def __init__(self, driver_class, **kwargs):
        self.driver = driver_class(**kwargs)
        
    def new_session(self, frontend_url, grpc_port, timeout=10):
        """Create a new session.
        
        You can use :obj:`carta.client.Session.new`, which wraps this method.
        
        Parameters
        ----------
        frontend_url : string
            The URL of the frontend.
        grpc_port : number
            The gRPC port on which the CARTA backend is listening. TODO: this should be deprecated when the frontend logs the gRPC port.
        timeout : number
            The number of seconds to spend checking the frontend log for connection information. 10 seconds by default.
            
        Returns
        -------
        :obj:`carta.client.Session`
            A session object connected to a new frontend session running in this browser.
        """
        # TODO: the gRPC port should be sent to the frontend by the backend and logged by the frontend
        self.driver.get(frontend_url)
        
        backend_host = None
        session_id = None
        
        start = time.time()
        now = start
        
        while (backend_host is None or session_id is None) and now - start < timeout:
            for entry in self.driver.get_log('browser'):
                message = entry["message"]
                
                m = re.search('"Connecting to (?:default|override) URL: wss?://(.+?):\d+"', message)
                if m:
                    backend_host = m.group(1)
                else:
                    m = re.search('"Connected with session ID (\d+)"', message)
                    if m:
                        session_id = int(m.group(1))
                        
            now = time.time()
        
        if backend_host is None or session_id is None:
            raise CartaScriptingException("Could not parse CARTA backend host and session ID from browser console log.")
        
        return Session(backend_host, grpc_port, session_id, browser=self)
    
    def close(self):
        """Shut down the browser driver."""
        self.driver.quit()


class ChromeHeadless(Browser):
    """Chrome or Chromium running headless, using the SwiftShader renderer for WebGL."""
    def __init__(self):
        chrome_options = Options()
        chrome_options.add_argument("--use-gl=swiftshader")
        chrome_options.add_argument("--headless")
        
        d = DesiredCapabilities.CHROME
        d['goog:loggingPrefs'] = { 'browser':'ALL' }
        
        super().__init__(webdriver.Chrome, options=chrome_options, desired_capabilities=d)


# TODO also add the option to open in a new window or tab of an existing browser:

class Chrome(Browser):
    pass # TODO

class Firefox(Browser):
    pass # TODO

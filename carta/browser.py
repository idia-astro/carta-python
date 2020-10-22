"""This module provides browser objects which can be used to create new sessions. It depends on the `selenium` library. The desired browser and its corresponding web driver also have to be installed."""

import re
import time

from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.common.exceptions import ElementClickInterceptedException, NoSuchElementException

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
        
        while (backend_host is None or session_id is None):
            if time.time() - start > timeout:
                break
            
            # This is a horrible temporary hack which should be replaced by more easily accessible elements
            try:
                log_button = self.driver.find_element_by_id("logButton")
            except NoSuchElementException:
                time.sleep(1)
                continue # retry
            
            try:
                log_button.click()
            except ElementClickInterceptedException:
                try:
                    self.driver.find_element_by_class_name("bp3-dialog-close-button").click()
                except (NoSuchElementException, ElementClickInterceptedException):
                    time.sleep(1)
                    continue # retry
                
                try:
                    log_button.click()
                except ElementClickInterceptedException:
                    time.sleep(1)
                    continue # retry
            
            log_entries = self.driver.find_element_by_class_name("log-entry-list")
            
            m = re.search(r"Connected to server wss?://(.*?):\d+ with session ID (\d+)", log_entries.text)
            if m:
                backend_host = m.group(1)
                session_id = int(m.group(2))
        
        if backend_host is None or session_id is None:
            self.close()
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
        super().__init__(webdriver.Chrome, options=chrome_options)


class Chrome(Browser):
    """Chrome or Chromium, no special options."""
    def __init__(self):
        super().__init__(webdriver.Chrome)


class Firefox(Browser):
    """Firefox, no special options."""
    def __init__(self):
        super().__init__(webdriver.Firefox)

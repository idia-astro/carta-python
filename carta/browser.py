"""This module provides browser objects which can be used to create new sessions. It depends on the `selenium` library. The desired browser and its corresponding web driver also have to be installed."""

import re
import time

from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.common.exceptions import ElementClickInterceptedException, NoSuchElementException

from .util import CartaScriptingException, logger
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
    
    def new_session(self, frontend_url, grpc_port=None, timeout=10, force_legacy=False):
        """Create a new session.
        
        You can use :obj:`carta.client.Session.new`, which wraps this method.
        
        Parameters
        ----------
        frontend_url : string
            The URL of the frontend.
        grpc_port : number, optional
            The gRPC port on which the CARTA backend is listening. This is only used for legacy CARTA versions; in newer versions this value is parsed automatically from the frontend.
        timeout : number
            The number of seconds to spend parsing the frontend for connection information. 10 seconds by default. If the attempt times out and `grpc_port` is set, an additional attempt will be made to use the legacy method to parse the remaining information from the frontend.
        force_legacy : boolean
            If this is set, we assume that we're connecting to a legacy CARTA version, and we skip the attempt to parse the frontend using the new method. `grpc_port` must be set if this option is used.
            
        Returns
        -------
        :obj:`carta.client.Session`
            A session object connected to a new frontend session running in this browser.
        """
        # TODO: the gRPC port should be sent to the frontend by the backend and logged by the frontend
        self.driver.get(frontend_url)
        
        backend_host = None
        session_id = None
        parsed_grpc_port = None
        
        if not force_legacy:
            start = time.time()
            last_error = ""
            
            while (backend_host is None or parsed_grpc_port is None or session_id is None):
                if time.time() - start > timeout:
                    break
                
                try:
                    # We can't use .text because Selenium is too clever to return the text of invisible elements.
                    backend_url = self.driver.find_element_by_id("info-server-url").get_attribute("textContent")
                    m = re.match(r"wss?://(.*?):\d+", backend_url)
                    if m:
                        backend_host = m.group(1)
                    else:
                        last_error = f"Could not parse backend host from url string '{backend_url}'."
                    
                    parsed_grpc_port = int(self.driver.find_element_by_id("info-grpc-port").get_attribute("textContent"))
                    session_id = int(self.driver.find_element_by_id("info-session-id").get_attribute("textContent"))
                except (NoSuchElementException, ValueError) as e:
                    last_error = str(e)
                    time.sleep(1)
                    continue # retry
            
            if backend_host is not None and parsed_grpc_port is not None and session_id is not None:
                return Session(backend_host, parsed_grpc_port, session_id, browser=self)
                        
            logger.warning(f"Could not use new method to parse connection information from CARTA frontend session. Falling back to legacy method. Last error: {last_error}")
            
            backend_host = None
            session_id = None
        
        if grpc_port is None:
            self.close()
            raise CartaScriptingException("Cannot use legacy method to parse connection information from CARTA frontend session. A gRPC port parameter must be provided.")
            
        start = time.time()
        
        while (backend_host is None or session_id is None):
            if time.time() - start > timeout:
                break
            
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
            raise CartaScriptingException("Could not parse CARTA backend host and session ID from frontend.")
        
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

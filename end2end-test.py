#!/usr/bin/python3
"""
Copyright 2023, University of Freiburg,
Chair of Algorithms and Data Structures
Author: Hannah Bast <bast@cs.uni-freiburg.de>
"""
import json
import time
import re
import os

from selenium.webdriver.firefox.options import Options
from selenium.webdriver.firefox.firefox_binary import FirefoxBinary
# from selenium.webdriver.chrome.options import Options
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.common.by import By
from selenium import webdriver

import argparse
import logging
import sys


class Hint:
    def __init__(self, text):
        self.fulltext = text
        self.database_type, self.database_id, self.name_language_pairs = self.parse(text)
        self.primary_name = self.name_language_pairs[0][0]

    def parse(self, text):
        database_type, database_id = None, None
        name_language_pairs = []

        parts = text.split('/')
        for part in parts:
            elements = re.split(r'["@]+', part.strip())
            if not database_type:
                database_type, database_id = re.search(r'(\w+):([A-Z]\d+)', elements[0]).groups()
            name = elements[1]
            language = elements[2]
            name_language_pairs.append((name, language))

        return database_type, database_id, name_language_pairs

    def get_names(self):
        return [pair[0] for pair in self.name_language_pairs]


# Global log with custom formatter, inspired by several posts on Stackoverflow.
class MyFormatter(logging.Formatter):
    def __init__(self):
        super().__init__(datefmt="%Y-%m-%d %H:%M:%S")

    def format(self, record):
        format_orig = self._style._fmt
        fmt_begin, fmt_end = "", ""
        if record.levelno == logging.ERROR:
            fmt_begin, fmt_end = "\x1b[31m", "\x1b[0m"
        elif record.levelno == logging.WARN:
            fmt_begin, fmt_end = "\x1b[35m", "\x1b[0m"
        fmt = "%(asctime)s.%(msecs)03d %(levelname)-5s %(message)s"
        self._style._fmt = fmt_begin + fmt + fmt_end
        result = logging.Formatter.format(self, record)
        self._style._fmt = format_orig
        return result


log = logging.getLogger("e2e test logger")
log.setLevel(logging.INFO)
handler = logging.StreamHandler()
handler.setFormatter(MyFormatter())
log.addHandler(handler)


class QleverUiTester:
    """
    Class or testing the Qlever UI.

    NOTE: The basic structure of this code is taken from
    https://github.com/ad-freiburg/hisinone-scraper
    """

    def __init__(self, headless, url, test_case_path, num_retries):
        """
        Basic settings and open the browser window.
        """

        self.headless = headless
        self.url = url
        self.num_retries = num_retries
        self.timeout_loading = 5

        self.test_cases_hints = []
        self.test_cases_examples = []
        self.init_test_cases(test_case_path)

        options = Options()
        if self.headless:
            log.info("Running in \x1b[1mheadless\x1b[0m mode")
            options.add_argument("-headless")
        else:
            log.info("Not headless, rerun with --headless to activate")
        log.info("Initializing webdriver ...")
        # options.binary = FirefoxBinary("/usr/bin/firefox")
        self.driver = webdriver.Firefox(options=options)
        # self.driver = webdriver.Chrome(options=options)
        # self.driver.set_window_position(100, 0)
        # self.driver.set_window_size(1400, 600)

    def done(self):
        """
        Close the browser window if it's still there.
        """
        input()
        log.info("Shutting down...")
        try:
            self.driver.close()
        except Exception:
            pass

    def init_test_cases(self, test_case_path):
        try:
            with open(test_case_path, 'r') as file:
                data = json.load(file)
                self.test_cases_hints = data.get("Testcases_Hints", [])
                self.test_cases_examples = data.get("Testcases_Examples", [])
        except:
            log.error("Could not initialize test cases.")

    def init_page(self):
        for i in range(self.num_retries):
            try:
                self.driver.get(self.url)
                WebDriverWait(self.driver, self.timeout_loading).until(
                    EC.presence_of_element_located((By.ID, "query")))
                log.info(f"Page {self.url} loaded successfully")
                break
            except Exception as e:
                if i < self.num_retries - 1:
                    log.info(f"Loading page failed"
                             f" (attempt {i + 1} of {self.num_retries}"
                             f", error: \"{str(e)}\")"
                             f", trying again ...")
                else:
                    log.error("Aborting after %d retries." % self.num_retries)
                    self.done()
                    sys.exit(1)

    def send_to_textfield(self, text):
        textfield = self.driver.find_element(By.XPATH, "/html/body/div[1]/div[5]/div/div[1]/div/div[1]/textarea")
        textfield.send_keys(text)

    def get_hints(self):
        for i in range(10):
            # wait until there are hints not starting with ? and then return them
            # alternative: get all network requests and wait till all have a responseEnd (are answered)
            #network_requests = self.driver.execute_script("var performance = window.performance || window.mozPerformance || window.msPerformance || window.webkitPerformance || {}; var network = performance.getEntries() || {}; return network;")

            time.sleep(0.5)
            try:
                hint_window = self.driver.find_element(By.XPATH, "/html/body/ul")
            except:
                log.info("Waiting for autocompletion hints...")
                continue

            hints = hint_window.find_elements(By.CLASS_NAME, "CodeMirror-hint")

            for hint in hints:
                if hint.text[0] != "?":
                    return hints
        log.info("No hints were shown")
        return []

    def test(self):
        """
        Running through different ui tests
        """
        self.test_examples()
        self.test_hints()

    def test_examples(self):
        """
        Testing the "Examples" function
        """
        for test_case in self.test_cases_examples:
            log.info("----------")
            log.info("Starting with Example Test %s" % test_case.get('name'))
            self.init_page()

            examples_button = self.driver.find_element(By.XPATH, "/html/body/div[1]/div[5]/div/div[3]/div[2]/button[4]")
            if not examples_button:
                log.warning("Test Case %s: Could not find the examples button" % test_case.get('name'))
                log.warning("Test Case %s: Testing examples button failed" % test_case.get('name'))
                continue
            examples_button.click()

            dropdown_menu = self.driver.find_element(By.XPATH, "/html/body/div[1]/div[5]/div/div[3]/div[2]/ul")
            if not dropdown_menu or not dropdown_menu.is_displayed():
                log.warning("Test Case %s: No examples were shown" % test_case.get('name'))
                log.warning("Test Case %s: Testing examples button failed" % test_case.get('name'))
                continue

            example = dropdown_menu.find_element(By.XPATH, "//span[contains(text(), '%s')]" % test_case.get('input'))
            if not example:
                log.warning('Test Case %s: Did not find "%s" example' % (test_case.get('name'), test_case.get('input')))
                log.warning("Test Case %s: Testing examples button failed" % test_case.get('name'))
                continue
            example.click()

            text = self.driver.find_element(By.XPATH, "/html/body/div[1]/div[5]/div/div[1]/div/div[6]/div[1]/div/div/div/div[5]")
            lines = text.find_elements(By.XPATH, "//span[@role]")
            expected_output = test_case.get('output').get('lines')
            for i in range(len(expected_output)):
                if lines[i].text != expected_output[i]:
                    log.warning('Test Case %s (line %s/%s): displayed\n"%s"\ninstead of\n"%s"' %
                                (test_case.get('name'), i + 1, len(expected_output), lines[i].text, expected_output[i]))
                    log.warning('Test Case %s failed' % test_case.get('name'))
                    break
            else:
                log.info('Test Case %s finished successfully')


    def test_hints(self):
        """
        Running through different hint tests.
        """
        for test_case in self.test_cases_hints:
            log.info("----------")
            log.info("Starting with Hint Test %s" % test_case.get('name'))
            self.init_page()
            self.send_to_textfield(test_case.get('input'))
            unprocessed_hints = self.get_hints()

            hints = [Hint(unprocessed_hint.text) for unprocessed_hint in unprocessed_hints]
            expected_hints = test_case.get('output').get('hints')
            hints_found = []
            hints_not_found = []

            #for hint in hints:
            #    print('["%s", "%s"],' % (hint.database_id, hint.primary_name))

            for i in range(len(expected_hints)):
                if hints[i].database_id in expected_hints[i]:
                    hints_found.append(hints[i])
                    log.info('Test Case %s (%s/%s): Hint %s "%s" displayed correctly' %
                             (test_case.get('name'), i + 1, len(expected_hints),
                              hints[i].database_id, hints[i].primary_name))
                else:
                    hints_not_found.append(hints[i])
                    log.warning('Test Case %s (%s/%s): Hint %s "%s" displayed instead of %s "%s"' %
                                (test_case.get('name'), i + 1, len(expected_hints),
                                 hints[i].database_id, hints[i].primary_name,
                                 expected_hints[i][0], expected_hints[i][1]))

            if hints_not_found:
                log.warning('Test Case %s: %s tests failed' % (test_case.get('name'), len(hints_not_found)))
            else:
                log.info('Test Case %s: completed successfully' % test_case.get('name'))

        log.info("All Test Cases are finished.")


class MyArgumentParser(argparse.ArgumentParser):
    """
    Override the error message so that it prints the full help text if the
    script is called without arguments or with a wrong argument.
    """

    def error(self, message):
        print("ArgumentParser: %s\n" % message)
        self.print_help()
        sys.exit(1)


if __name__ == "__main__":

    # Setup parser and basic usage information.
    parser = MyArgumentParser(
            epilog="Example invocation: python3 qlever-end2end",
            formatter_class=argparse.RawDescriptionHelpFormatter)

    # Command line arguments.
    parser.add_argument(
            "--not-headless", dest="not_headless", action="store_true",
            help="Run browser in headful mode (default: headless mode)")
    parser.add_argument(
            "--url", dest="url", type=str,
            default="https://qlever.cs.uni-freiburg.de",
            help="The URL of the QLever UI (may redirect)")
    parser.add_argument(
        "--test-case-path", dest="test_case_path", type=str,
        default="end2end-testcases.json",
        help="A path to a JSON File with the autocompletion testcases to check")
    parser.add_argument(
            "--num-retries", dest="num_retries", type=int, default=5,
            help="Number of retries for loading a page")
    parser.add_argument(
            "--log-level", dest="log_level", type=str,
            choices=["INFO", "DEBUG", "ERROR"], default="INFO",
            help="Log level (INFO, DEBUG, ERROR)")
    args = parser.parse_args(sys.argv[1:])

    # Set log level and show it.
    log.setLevel(eval("logging.%s" % args.log_level))
    print()
    log.info("Log level is \x1b[1m%s\x1b[0m" % args.log_level)

    # Test the QLever UI.
    qleverui_tester = QleverUiTester(not args.not_headless, args.url, args.test_case_path, args.num_retries)
    qleverui_tester.test()
    qleverui_tester.done()

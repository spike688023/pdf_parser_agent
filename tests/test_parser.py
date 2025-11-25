import unittest
from unittest.mock import MagicMock, patch
from src.pdf_parser import parser_agent, parse_pdf_file

class TestPDFParserAgent(unittest.TestCase):
    def test_tool_function(self):
        # We can't easily test the agent without an API key, but we can test the tool if we mock pdfplumber
        with patch('pdfplumber.open') as mock_open:
            mock_pdf = MagicMock()
            mock_page = MagicMock()
            mock_page.extract_text.return_value = "Test content"
            mock_pdf.pages = [mock_page]
            mock_open.return_value.__enter__.return_value = mock_pdf
            
            text = parse_pdf_file("dummy.pdf")
            self.assertIn("Test content", text)

    def test_agent_structure(self):
        self.assertEqual(parser_agent.name, "parser_agent")
        self.assertTrue(len(parser_agent.tools) > 0)

if __name__ == '__main__':
    unittest.main()

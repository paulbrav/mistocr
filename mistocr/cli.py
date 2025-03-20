"""
Command line interface for mistocr.
"""

import os
import sys
import click
from pathlib import Path
from typing import List, Optional
import tqdm

from mistocr import __version__
from mistocr.config import ensure_api_key
from mistocr.api import process_document
from mistocr.formatter import format_as_markdown, format_as_text, format_as_pdf


def parse_pages(pages_str: Optional[str]) -> Optional[List[int]]:
    """
    Parse pages string into a list of page indices.
    
    Accepts formats like: "0,1,2", "0-5", "0,2-5,7"
    
    Args:
        pages_str: String representation of pages
        
    Returns:
        List of page indices or None if all pages
    """
    if not pages_str:
        return None
    
    pages = []
    parts = pages_str.split(',')
    
    for part in parts:
        if '-' in part:
            start, end = part.split('-')
            pages.extend(range(int(start), int(end) + 1))
        else:
            pages.append(int(part))
    
    return pages


def validate_file(ctx, param, value):
    """Validate that the file exists and has supported extension."""
    if not value:
        return None
    
    file_path = Path(value)
    if not file_path.exists():
        raise click.BadParameter(f"File does not exist: {value}")
    
    # Check file extension
    ext = file_path.suffix.lower()
    if ext not in ['.pdf', '.pptx']:
        raise click.BadParameter(
            f"Unsupported file format: {ext}. Supported formats are: .pdf, .pptx"
        )
    
    return str(file_path)


@click.command()
@click.version_option(version=__version__)
@click.argument('file', required=True, callback=validate_file)
@click.option(
    '-o', '--output',
    type=click.Path(),
    help='Output file path. If not specified, output will be printed to stdout.'
)
@click.option(
    '-f', '--format',
    type=click.Choice(['markdown', 'text', 'pdf']),
    default='markdown',
    help='Output format (default: markdown)'
)
@click.option(
    '--pages',
    help='Pages to process (e.g., "0,1,3-5"). Starts from 0.'
)
@click.option(
    '--images/--no-images',
    default=True,
    help='Include images in output (default: yes)'
)
@click.option(
    '--images-dir',
    type=click.Path(),
    help='Directory to save extracted images instead of embedding them'
)
def main(
    file: str,
    output: Optional[str],
    format: str,
    pages: Optional[str],
    images: bool,
    images_dir: Optional[str]
):
    """
    Process documents using Mistral AI OCR API.
    
    FILE is the path to the document to process (PDF or PPTX).
    """
    # Check and get API key
    api_key = ensure_api_key()
    if not api_key:
        click.echo("No API key provided. Exiting.")
        sys.exit(1)
    
    # Parse pages
    parsed_pages = parse_pages(pages)
    
    # Process file
    click.echo(f"Processing document: {file}")
    with tqdm.tqdm(total=100, desc="OCR Processing") as pbar:
        pbar.update(10)  # Show initial progress
        
        try:
            # Call API
            include_images_in_api = images or (images_dir is not None)
            result = process_document(
                file_path=file,
                api_key=api_key,
                pages=parsed_pages,
                include_images=include_images_in_api
            )
            pbar.update(70)  # Update progress
            
            # Determine output format from file extension if not explicitly specified
            if output and output.lower().endswith('.pdf') and format == 'markdown':
                format = 'pdf'
            
            # Format response
            if format == 'markdown':
                formatted = format_as_markdown(
                    result,
                    include_images=images,
                    output_dir=images_dir
                )
                output_is_binary = False
            elif format == 'text':
                formatted = format_as_text(result)
                output_is_binary = False
            elif format == 'pdf':
                if not output:
                    click.echo("PDF output requires an output file path. Use -o/--output option.", err=True)
                    sys.exit(1)
                format_as_pdf(
                    result,
                    output_path=output,
                    include_images=images
                )
                formatted = f"PDF output written to: {output}"
                output_is_binary = True
            
            pbar.update(20)  # Complete progress
        except Exception as e:
            click.echo(f"Error: {str(e)}", err=True)
            sys.exit(1)
    
    # Output result
    if output and not output_is_binary:
        with open(output, 'w', encoding='utf-8') as f:
            f.write(formatted)
        click.echo(f"Output written to: {output}")
    elif not output_is_binary:
        click.echo("\n" + formatted)


if __name__ == '__main__':
    main() 
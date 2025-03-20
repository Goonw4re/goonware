import os
import sys
import argparse
import logging
from .converter import GoonConverter

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger(__name__)

def setup_argparse():
    """Set up argument parser for the command line interface"""
    parser = argparse.ArgumentParser(
        description='Convert zip files to goon files for use with Goonware'
    )
    
    # Add subparsers for different commands
    subparsers = parser.add_subparsers(dest='command', help='Command to run')
    
    # Convert command
    convert_parser = subparsers.add_parser('convert', help='Convert a single zip file to goon format')
    convert_parser.add_argument('zip_file', help='Path to the zip file to convert')
    convert_parser.add_argument('--delete', action='store_true', help='Delete the original zip file after conversion')
    convert_parser.add_argument('--output-dir', help='Custom output directory for the goon file')
    
    # Batch convert command
    batch_parser = subparsers.add_parser('batch', help='Convert all zip files in the models directory')
    batch_parser.add_argument('--delete', action='store_true', help='Delete original zip files after conversion')
    batch_parser.add_argument('--models-dir', help='Custom models directory path')
    
    return parser

def main():
    """Main entry point for the CLI"""
    parser = setup_argparse()
    args = parser.parse_args()
    
    if not args.command:
        parser.print_help()
        return
    
    # Initialize converter with custom models directory if provided
    models_dir = None
    if hasattr(args, 'models_dir') and args.models_dir:
        models_dir = args.models_dir
    elif hasattr(args, 'output_dir') and args.output_dir:
        models_dir = args.output_dir
        
    converter = GoonConverter(models_dir)
    
    # Handle convert command
    if args.command == 'convert':
        zip_path = os.path.abspath(args.zip_file)
        logger.info(f"Converting {zip_path} to goon format")
        
        result = converter.convert_to_goon(zip_path, args.delete)
        
        if result:
            logger.info(f"Successfully converted to {result}")
        else:
            logger.error("Conversion failed")
            sys.exit(1)
    
    # Handle batch convert command
    elif args.command == 'batch':
        logger.info(f"Batch converting zip files in {converter.models_dir}")
        
        stats = converter.batch_convert(args.delete)
        
        logger.info(f"Batch conversion completed:")
        logger.info(f"  Total zip files found: {stats['total']}")
        logger.info(f"  Successfully converted: {stats['success']}")
        logger.info(f"  Failed conversions: {stats['failures']}")
        logger.info(f"  Skipped (already exist): {stats['skipped']}")
        
        if stats['failures'] > 0:
            logger.warning("Some conversions failed. Check the logs for details.")
            sys.exit(1)

if __name__ == '__main__':
    main() 
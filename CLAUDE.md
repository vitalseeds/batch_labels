# Batch label printer

Super simple fastapi app to print labels in batches.

Uses the python-zpl library to generate ZPL labels.

Designed to be print to the Zebra GK42D label printer over the local network,
but should work with any printer that supports ZPL.

Presents a single simple html form to enter an alphanumeric SKU, a batch number and number to print. Submitting the form generates the ZPL for the label and sends it to the printer.

Uses the [Labelary API](https://labelary.com/) to preview ZPL labels.

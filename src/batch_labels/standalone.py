"""Entry point for running batch-labels as a standalone server."""
import uvicorn


def main():
    uvicorn.run("batch_labels.main:app", host="0.0.0.0", port=8765, reload=False)


if __name__ == "__main__":
    main()

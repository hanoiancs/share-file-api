from app.app import create_app

app = create_app()
app.frontend("/", directory="dist")


def main():
    print("Internal Static Files API")


if __name__ == "__main__":
    main()

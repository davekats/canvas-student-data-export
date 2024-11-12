from subprocess import run

SINGLEFILE_BINARY_PATH = "./node_modules/single-file-cli/single-file"
CHROME_PATH = "C:/Program Files/Google\ Chrome/Application/chrome.exe" #Uncomment this and set your browser exe if it can't find yours.

def addQuotes(str):
    return "\"" + str.strip("\"") + "\""

def download_page(url, cookies_path, output_path, output_name_template = ""):
    args = [
        addQuotes(SINGLEFILE_BINARY_PATH),
        #"--browser-executable-path=" + addQuotes(CHROME_PATH.strip("\"")), #Uncomment this and set your browser exe if it can't find yours.
        "--browser-cookies-file=" + addQuotes(cookies_path),
        "--output-directory=" + addQuotes(output_path),
        addQuotes(url)
        ]

    if(output_name_template != ""):
        args.append("--filename-template=" + addQuotes(output_name_template))

    try:
        run(" ".join(args), shell=True)
    except Exception as e:
        print("Was not able to save the URL " + url + " using singlefile. The reported error was " + e.strerror)

#if __name__ == "__main__":
    #download_page("https://www.google.com/", "", "./output/test", "test.html")

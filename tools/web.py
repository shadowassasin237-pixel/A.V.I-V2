"""
A.V.I. Web Search Tool
"""

from ddgs import DDGS


class AVIWebSearch:

    def search(self, query: str, max_results=5):
        try:
            results = []

            with DDGS() as ddgs:
                search_results = ddgs.text(
                    query,
                    max_results=max_results
                )

                for result in search_results:
                    results.append({
                        "title": result.get("title", ""),
                        "link": result.get("href", ""),
                        "snippet": result.get("body", "")
                    })

            return results

        except Exception as error:
            return [{"error": str(error)}]


if __name__ == "__main__":
    web = AVIWebSearch()

    query = input("Search: ")

    results = web.search(query)

    print()
    print("A.V.I. Web Search Results")
    print("=" * 40)

    if not results:
        print("No results found.")

    for number, result in enumerate(results, start=1):

        if "error" in result:
            print("Error:", result["error"])
            continue

        print(f"\n{number}. {result['title']}")
        print(f"   {result['link']}")
        print(f"   {result['snippet']}")
        
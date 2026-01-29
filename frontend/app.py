import json
from typing import Optional
from urllib.parse import quote_plus

from backend.config import get

from fasthtml.components import (
    H1,
    H2,
    H3,
    Br,
    Div,
    Form,
    Img,
    NotStr,
    P,
    Hr,
    Span,
    Ul,
    Li,
    Strong,
    Iframe,
    Textarea,
)
from fasthtml.common import Input as HtmlInput
from fasthtml.xtend import A, Script
from lucide_fasthtml import Lucide
from shad4fast import Badge, Button, Input, Label, RadioGroup, RadioGroupItem, Separator

# JavaScript to check the input value and enable/disable the search button and radio buttons
check_input_script = Script(
    """
        window.onload = function() {
            const input = document.getElementById('search-input');
            const button = document.querySelector('[data-button="search-button"]');
            const radioGroupItems = document.querySelectorAll('button[data-ref="radio-item"]');  // Get all radio buttons
            
            function checkInputValue() {
                const isInputEmpty = input.value.trim() === "";
                button.disabled = isInputEmpty;  // Disable the submit button
                radioGroupItems.forEach(item => {
                    item.disabled = isInputEmpty;  // Disable/enable the radio buttons
                });
            }

            input.addEventListener('input', checkInputValue);  // Listen for input changes
            checkInputValue();  // Initial check when the page loads
        };
    """
)

# JavaScript to handle the image swapping, reset button, and active class toggling
image_swapping = Script(
    """
    document.addEventListener('click', function (e) {
        if (e.target.classList.contains('sim-map-button') || e.target.classList.contains('reset-button')) {
            const imgContainer = e.target.closest('.relative'); 
            const overlayContainer = imgContainer.querySelector('.overlay-container');
            const newSrc = e.target.getAttribute('data-image-src');
    
            // If it's a reset button, remove the overlay image
            if (e.target.classList.contains('reset-button')) {
                overlayContainer.innerHTML = '';  // Clear the overlay container, showing only the full image
            } else {
                // Create a new overlay image
                const img = document.createElement('img');
                img.src = newSrc;
                img.classList.add('overlay-image', 'absolute', 'top-0', 'left-0', 'w-full', 'h-full');
                overlayContainer.innerHTML = '';  // Clear any previous overlay
                overlayContainer.appendChild(img);  // Add the new overlay image
            }
    
            // Toggle active class on buttons
            const activeButton = document.querySelector('.sim-map-button.active');
            if (activeButton) {
                activeButton.classList.remove('active');
            }
            if (e.target.classList.contains('sim-map-button')) {
                e.target.classList.add('active');
            }
        }
    });
    """
)

toggle_text_content = Script(
    """
    function toggleTextContent(idx) {
        const textColumn = document.getElementById(`text-column-${idx}`);
        const imageTextColumns = document.getElementById(`image-text-columns-${idx}`);
        const toggleButton = document.getElementById(`toggle-button-${idx}`);
    
        if (textColumn.classList.contains('md-grid-text-column')) {
          // Hide the text column
          textColumn.classList.remove('md-grid-text-column');
          imageTextColumns.classList.remove('grid-image-text-columns');
          toggleButton.innerText = `Show Text`;
        } else {
          // Show the text column
          textColumn.classList.add('md-grid-text-column');
          imageTextColumns.classList.add('grid-image-text-columns');
          toggleButton.innerText = `Hide Text`;
        }
    }
    """
)

_autocomplete_min_chars = get("autocomplete", "min_chars")
_autocomplete_max_items = get("autocomplete", "max_items")
autocomplete_script = Script(
    """
    document.addEventListener('DOMContentLoaded', function() {
        const input = document.querySelector('#search-input');
        const awesomplete = new Awesomplete(input, { minChars: """
    + str(_autocomplete_min_chars)
    + """, maxItems: """
    + str(_autocomplete_max_items)
    + """ });

        input.addEventListener('input', function() {
            if (this.value.length >= 1) {
                // Use template literals to insert the input value dynamically in the query parameter
                fetch(`/suggestions?query=${encodeURIComponent(this.value)}`)
                    .then(response => response.json())
                    .then(data => {
                        // Update the Awesomplete list dynamically with fetched suggestions
                        awesomplete.list = data.suggestions;
                    })
                    .catch(err => console.error('Error fetching suggestions:', err));
            }
        });
    });
    """
)

dynamic_elements_scrollbars = Script(
    """
    (function () {
        const { applyOverlayScrollbars, getScrollbarTheme } = OverlayScrollbarsManager;

        function applyScrollbarsToDynamicElements() {
            const scrollbarTheme = getScrollbarTheme();

            // Apply scrollbars to dynamically loaded result-text-full and result-text-snippet elements
            const resultTextFullElements = document.querySelectorAll('[id^="result-text-full"]');
            const resultTextSnippetElements = document.querySelectorAll('[id^="result-text-snippet"]');

            resultTextFullElements.forEach(element => {
                applyOverlayScrollbars(element, scrollbarTheme);
            });

            resultTextSnippetElements.forEach(element => {
                applyOverlayScrollbars(element, scrollbarTheme);
            });
        }

        // Apply scrollbars after dynamic content is loaded (e.g., after search results)
        applyScrollbarsToDynamicElements();

        // Observe changes in the 'dark' class to adjust the theme dynamically if needed
        const observer = new MutationObserver(applyScrollbarsToDynamicElements);
        observer.observe(document.documentElement, { attributes: true, attributeFilter: ['class'] });
    })();
    """
)

submit_form_on_radio_change = Script(
    """
    document.addEventListener('click', function (e) {
        // if target has data-ref="radio-item" and type is button
        if (e.target.getAttribute('data-ref') === 'radio-item' && e.target.type === 'button') {
            console.log('Radio button clicked');
            const form = e.target.closest('form');
            form.submit();
        }
    });
    """
)


def ShareButtons():
    title = "Visual RAG over PDFs with Vespa and ColPali"
    url = "https://huggingface.co/spaces/vespa-engine/colpali-vespa-visual-retrieval"
    return Div(
        A(
            Img(src="/static/img/linkedin.svg", aria_hidden="true", cls="h-[21px]"),
            "Share on LinkedIn",
            href=f"https://www.linkedin.com/sharing/share-offsite/?url={quote_plus(url)}",
            rel="noopener noreferrer",
            target="_blank",
            cls="bg-[#0A66C2] text-white inline-flex items-center gap-x-1.5 px-2.5 py-1.5 border rounded-md text-sm font-semibold",
        ),
        A(
            Img(src="/static/img/x.svg", aria_hidden="true", cls="h-[21px]"),
            "Share on X",
            href=f"https://twitter.com/intent/tweet?text={quote_plus(title)}&url={quote_plus(url)}",
            rel="noopener noreferrer",
            target="_blank",
            cls="bg-black text-white inline-flex items-center gap-x-1.5 px-2.5 py-1.5 border rounded-md text-sm font-semibold",
        ),
        cls="flex items-center justify-center space-x-8 mt-5",
    )


def SearchBox(with_border=False, query_value="", ranking_value="hybrid"):
    grid_cls = "grid gap-2 items-center p-3 bg-muted w-full"

    if with_border:
        grid_cls = "grid gap-2 p-3 rounded-md border border-input bg-muted w-full ring-offset-background focus-within:outline-none focus-within:ring-2 focus-within:ring-ring focus-within:ring-offset-2 focus-within:border-input"

    return Form(
        Div(
            Lucide(
                icon="search", cls="absolute left-2 top-2 text-muted-foreground z-10"
            ),
            Input(
                placeholder="Enter your search query...",
                name="query",
                value=query_value,
                id="search-input",
                cls="text-base pl-10 border-transparent ring-offset-transparent ring-0 focus-visible:ring-transparent bg-white dark:bg-background awesomplete",
                data_list="#suggestions",
                style="font-size: 1rem",
                autofocus=True,
            ),
            cls="relative",
        ),
        Div(
            Div(
                Span("Ranking by:", cls="text-muted-foreground text-xs font-semibold"),
                RadioGroup(
                    Div(
                        RadioGroupItem(value="colpali", id="colpali"),
                        Label("ColPali", htmlFor="ColPali"),
                        cls="flex items-center space-x-2",
                    ),
                    Div(
                        RadioGroupItem(value="bm25", id="bm25"),
                        Label("BM25", htmlFor="BM25"),
                        cls="flex items-center space-x-2",
                    ),
                    Div(
                        RadioGroupItem(value="hybrid", id="hybrid"),
                        Label("Hybrid ColPali + BM25", htmlFor="Hybrid ColPali + BM25"),
                        cls="flex items-center space-x-2",
                    ),
                    name="ranking",
                    default_value=ranking_value,
                    cls="grid-flow-col gap-x-5 text-muted-foreground",
                    # Submit form when radio button is clicked
                ),
                cls="grid grid-flow-col items-center gap-x-3 border border-input px-3 rounded-sm",
            ),
            Button(
                Lucide(icon="arrow-right", size="21"),
                size="sm",
                type="submit",
                data_button="search-button",
                disabled=True,
            ),
            cls="flex justify-between",
        ),
        check_input_script,
        autocomplete_script,
        submit_form_on_radio_change,
        action=f"/search?query={quote_plus(query_value)}&ranking={quote_plus(ranking_value)}",
        method="GET",
        hx_get="/fetch_results",  # As the component is a form, input components query and ranking are sent as query parameters automatically, see https://htmx.org/docs/#parameters
        hx_trigger="load",
        hx_target="#search-results",
        hx_swap="outerHTML",
        hx_indicator="#loading-indicator",
        cls=grid_cls,
    )


def SampleQueries():
    sample_queries = [
        "What percentage of the funds unlisted real estate investments were in Switzerland 2023?",
        "Gender balance at level 4 or above in NY office 2023?",
        "Number of graduate applications trend 2021-2023",
        "Total amount of fixed salaries paid in 2023?",
        "Proportion of female new hires 2021-2023?",
        "child jumping over puddle",
        "hula hoop kid",
    ]

    query_badges = []
    for query in sample_queries:
        query_badges.append(
            A(
                Badge(
                    Div(
                        Lucide(
                            icon="text-search", size="18", cls="text-muted-foreground"
                        ),
                        Span(query, cls="text-base font-normal"),
                        cls="flex gap-2 items-center",
                    ),
                    variant="outline",
                    cls="text-base font-normal text-muted-foreground hover:border-black dark:hover:border-white",
                ),
                href=f"/search?query={quote_plus(query)}",
                cls="no-underline",
            )
        )

    return Div(*query_badges, cls="grid gap-2 justify-items-center")


def Hero():
    return Div(
        H1(
            "Visual RAG over PDFs",
            cls="text-5xl md:text-6xl font-bold tracking-wide md:tracking-wider bg-clip-text text-transparent bg-gradient-to-r from-black to-slate-700 dark:from-white dark:to-slate-300 animate-fade-in",
        ),
        P(
            "See how Vespa and ColPali can be used for Visual RAG in this demo",
            cls="text-base md:text-2xl text-muted-foreground md:tracking-wide",
        ),
        cls="grid gap-5 text-center",
    )


def Home():
    return Div(
        Div(
            Hero(),
            SearchBox(with_border=True),
            SampleQueries(),
            ShareButtons(),
            cls="grid gap-8 content-start mt-[13vh]",
        ),
        cls="grid w-full h-full max-w-screen-md gap-4 mx-auto",
    )


def LinkResource(text, href):
    return Li(
        A(
            Lucide(icon="external-link", size="18"),
            text,
            href=href,
            target="_blank",
            cls="flex items-center gap-1.5 hover:underline bold text-md",
        ),
    )


def AboutThisDemo():
    resources = [
        {
            "text": "Vespa Blog: How we built this demo",
            "href": "https://blog.vespa.ai/visual-rag-in-practice",
        },
        {
            "text": "Notebook to set up Vespa application and feed dataset",
            "href": "https://pyvespa.readthedocs.io/en/latest/examples/visual_pdf_rag_with_vespa_colpali_cloud.html",
        },
        {
            "text": "Web App (FastHTML) Code",
            "href": "https://github.com/vespa-engine/sample-apps/tree/master/visual-retrieval-colpali",
        },
        {
            "text": "Vespa Blog: Scaling ColPali to Billions",
            "href": "https://blog.vespa.ai/scaling-colpali-to-billions/",
        },
        {
            "text": "Vespa Blog: Retrieval with Vision Language Models",
            "href": "https://blog.vespa.ai/retrieval-with-vision-language-models-colpali/",
        },
    ]
    return Div(
        H1(
            "About This Demo",
            cls="text-3xl md:text-5xl font-bold tracking-wide md:tracking-wider",
        ),
        P(
            "This demo showcases a Visual Retrieval-Augmented Generation (RAG) application over PDFs using ColPali embeddings in Vespa, built entirely in Python, using FastHTML. The code is fully open source.",
            cls="text-base",
        ),
        Img(
            src="/static/img/colpali_child.png",
            alt="Example of token level similarity map",
            cls="w-full",
        ),
        H2("Resources", cls="text-2xl font-semibold"),
        Ul(
            *[
                LinkResource(resource["text"], resource["href"])
                for resource in resources
            ],
            cls="space-y-2 list-disc pl-5",
        ),
        H2("Architecture Overview", cls="text-2xl font-semibold"),
        Img(
            src="/static/img/visual-retrieval-demoapp-arch.png",
            alt="Architecture Overview",
            cls="w-full",
        ),
        Ul(
            Li(
                Strong("Vespa Application: "),
                "Vespa Application that handles indexing, search, ranking and queries, leveraging features like phased ranking and multivector MaxSim calculations.",
            ),
            Li(
                Strong("Frontend: "),
                "Built with FastHTML, offering a professional and responsive user interface without the complexity of separate frontend frameworks.",
            ),
            Li(
                Strong("Backend: "),
                "Also built with FastHTML. Handles query embedding inference using ColPali, serves static files, and is responsible for orchestrating interactions between Vespa and the frontend.",
            ),
            Li(
                Strong("OpenRouter API: "),
                "VLM for the AI response (via OpenRouter), providing responses based on the top results from Vespa.",
                cls="list-disc list-inside",
            ),
            H2("User Experience Highlights", cls="text-2xl font-semibold"),
            Ul(
                Li(
                    Strong("Fast and Responsive: "),
                    "Optimized for quick loading times, with phased content delivery to display essential information immediately while loading detailed data in the background.",
                ),
                Li(
                    Strong("Similarity Maps: "),
                    "Provides visual highlights of the most relevant parts of a page in response to a query, enhancing interpretability.",
                ),
                Li(
                    Strong("Type-Ahead Suggestions: "),
                    "Offers query suggestions to assist users in formulating effective searches.",
                ),
                cls="list-disc list-inside",
            ),
            cls="grid gap-5",
        ),
        H2("Dataset", cls="text-2xl font-semibold"),
        P(
            "The dataset used in this demo is retrieved from reports published by the Norwegian Government Pension Fund Global. It contains 6,992 pages from 116 PDF reports (2000–2024). The information is often presented in visual formats, making it an ideal dataset for visual retrieval applications.",
            cls="text-base",
        ),
        Iframe(
            src="https://huggingface.co/datasets/vespa-engine/gpfg-QA/embed/viewer",
            frameborder="0",
            width="100%",
            height="500",
        ),
        Hr(),  # To add some margin to bottom. Probably a much better way to do this, but the mb-[16vh] class doesn't seem to be applied
        cls="w-full h-full max-w-screen-md gap-4 mx-auto mt-[8vh] mb-[16vh] grid gap-8 content-start",
    )


def Search(request, search_results=[]):
    query_value = request.query_params.get("query", "").strip()
    ranking_value = request.query_params.get("ranking", "hybrid")
    return Div(
        Div(
            Div(
                SearchBox(query_value=query_value, ranking_value=ranking_value),
                Div(
                    LoadingMessage(),
                    id="search-results",  # This will be replaced by the search results
                ),
                cls="grid",
            ),
            cls="grid",
        ),
    )


def LoadingMessage(display_text="Retrieving search results"):
    return Div(
        Lucide(icon="loader-circle", cls="size-5 mr-1.5 animate-spin"),
        Span(display_text, cls="text-base text-center"),
        cls="p-10 text-muted-foreground flex items-center justify-center",
        id="loading-indicator",
    )


def LoadingSkeleton():
    return Div(
        Div(cls="h-5 bg-muted"),
        Div(cls="h-5 bg-muted"),
        Div(cls="h-5 bg-muted"),
        cls="grid gap-2 animate-pulse",
    )


def SimMapButtonReady(query_id, idx, token, token_idx, img_src):
    return Button(
        token.replace("\u2581", ""),
        size="sm",
        data_image_src=img_src,
        id=f"sim-map-button-{query_id}-{idx}-{token_idx}-{token}",
        cls="sim-map-button pointer-events-auto font-mono text-xs h-5 rounded-none px-2",
    )


def SimMapButtonPoll(query_id, idx, token, token_idx):
    return Button(
        Lucide(icon="loader-circle", size="15", cls="animate-spin"),
        size="sm",
        disabled=True,
        hx_get=f"/get_sim_map?query_id={query_id}&idx={idx}&token={token}&token_idx={token_idx}",
        hx_trigger="every 0.5s",
        hx_swap="outerHTML",
        cls="pointer-events-auto text-xs h-5 rounded-none px-2",
    )


def SearchInfo(search_time, total_count):
    return (
        Div(
            Span(
                "Retrieved ",
                Strong(total_count),
                Span(" results"),
                Span(" in "),
                Strong(f"{search_time:.3f}"),  # 3 significant digits
                Span(" seconds."),
            ),
            cls="grid bg-background border-t text-sm text-center p-3",
        ),
    )


def SearchResult(
    results: list,
    query: str,
    query_id: Optional[str] = None,
    search_time: float = 0,
    total_count: int = 0,
):
    if not results:
        return Div(
            P(
                "No results found for your query.",
                cls="text-muted-foreground text-base text-center",
            ),
            cls="grid p-10",
        )

    doc_ids = []
    # Otherwise, display the search results
    result_items = []
    for idx, result in enumerate(results):
        fields = result["fields"]  # Extract the 'fields' part of each result
        doc_id = fields["id"]
        doc_ids.append(doc_id)
        blur_image_base64 = f"data:image/jpeg;base64,{fields['blur_image']}"

        sim_map_fields = {
            key: value
            for key, value in fields.items()
            if key.startswith(
                "sim_map_"
            )  # filtering is done before creating with 'should_filter_token'-function
        }

        # Generate buttons for the sim_map fields
        sim_map_buttons = []
        for key, value in sim_map_fields.items():
            token = key.split("_")[-2]
            token_idx = int(key.split("_")[-1])
            if value is not None:
                sim_map_base64 = f"data:image/jpeg;base64,{value}"
                sim_map_buttons.append(
                    SimMapButtonReady(
                        query_id=query_id,
                        idx=idx,
                        token=token,
                        token_idx=token_idx,
                        img_src=sim_map_base64,
                    )
                )
            else:
                sim_map_buttons.append(
                    SimMapButtonPoll(
                        query_id=query_id,
                        idx=idx,
                        token=token,
                        token_idx=token_idx,
                    )
                )

        # Add "Reset Image" button to restore the full image
        reset_button = Button(
            "Reset",
            variant="outline",
            size="sm",
            data_image_src=blur_image_base64,
            cls="reset-button pointer-events-auto font-mono text-xs h-5 rounded-none px-2",
        )

        tokens_icon = Lucide(icon="images", size="15")

        # Add "Tokens" button - this has no action, just a placeholder
        tokens_button = Button(
            tokens_icon,
            "Tokens",
            size="sm",
            cls="tokens-button flex gap-[3px] font-bold pointer-events-none font-mono text-xs h-5 rounded-none px-2",
        )

        result_items.append(
            Div(
                Div(
                    Div(
                        Lucide(icon="file-text"),
                        H2(fields["title"], cls="text-xl md:text-2xl font-semibold"),
                        Separator(orientation="vertical"),
                        Badge(
                            f"Relevance score: {result['relevance']:.4f}",
                            cls="flex gap-1.5 items-center justify-center",
                        ),
                        cls="flex items-center gap-2",
                    ),
                    Div(
                        Button(
                            "Hide Text",
                            size="sm",
                            id=f"toggle-button-{idx}",
                            onclick=f"toggleTextContent({idx})",
                            cls="hidden md:block",
                        ),
                    ),
                    cls="flex flex-wrap items-center justify-between bg-background px-3 py-4",
                ),
                Div(
                    Div(
                        Div(
                            tokens_button,
                            *sim_map_buttons,
                            reset_button,
                            cls="flex flex-wrap gap-px w-full pointer-events-none",
                        ),
                        Div(
                            Div(
                                Div(
                                    Img(
                                        src=blur_image_base64,
                                        hx_get=f"/full_image?doc_id={doc_id}",
                                        style="backdrop-filter: blur(5px);",
                                        hx_trigger="load",
                                        hx_swap="outerHTML",
                                        alt=fields["title"],
                                        cls="result-image w-full h-full object-contain",
                                    ),
                                    Div(
                                        cls="overlay-container absolute top-0 left-0 w-full h-full pointer-events-none"
                                    ),
                                    cls="relative w-full h-full",
                                ),
                                cls="grid bg-muted p-2",
                            ),
                            cls="block",
                        ),
                        id=f"image-column-{idx}",
                        cls="image-column relative bg-background px-3 py-5 grid-image-column",
                    ),
                    Div(
                        Div(
                            A(
                                Lucide(icon="external-link", size="18"),
                                f"PDF Source (Page {fields['page_number'] + 1})",
                                href=f"{fields['url']}#page={fields['page_number'] + 1}",
                                target="_blank",
                                cls="flex items-center gap-1.5 font-mono bold text-sm",
                            ),
                            *(
                                [
                                    A(
                                        Lucide(icon="download", size="18"),
                                        "Download Original PDF",
                                        href=f"/download_pdf?doc_id={doc_id}",
                                        target="_blank",
                                        cls="flex items-center gap-1.5 font-mono bold text-sm hover:underline",
                                    )
                                ]
                                if fields.get("s3_key")
                                else []
                            ),
                            cls="flex items-center justify-end gap-4",
                        ),
                        Div(
                            Div(
                                Div(
                                    Div(
                                        Div(
                                            H3(
                                                "Dynamic summary",
                                                cls="text-base font-semibold",
                                            ),
                                            P(
                                                NotStr(fields.get("snippet", "")),
                                                cls="text-highlight text-muted-foreground",
                                            ),
                                            cls="grid grid-rows-[auto_0px] content-start gap-y-3",
                                        ),
                                        id=f"result-text-snippet-{idx}",
                                        cls="grid gap-y-3 p-8 border border-dashed",
                                    ),
                                    Div(
                                        Div(
                                            Div(
                                                H3(
                                                    "Full text",
                                                    cls="text-base font-semibold",
                                                ),
                                                Div(
                                                    P(
                                                        NotStr(fields.get("text", "")),
                                                        cls="text-highlight text-muted-foreground",
                                                    ),
                                                    Br(),
                                                ),
                                                cls="grid grid-rows-[auto_0px] content-start gap-y-3",
                                            ),
                                            id=f"result-text-full-{idx}",
                                            cls="grid gap-y-3 p-8 border border-dashed",
                                        ),
                                        Div(
                                            cls="absolute inset-x-0 bottom-0 bg-gradient-to-t from-[#fcfcfd] dark:from-[#1c2024] pt-[7%]"
                                        ),
                                        cls="relative grid",
                                    ),
                                    cls="grid grid-rows-[1fr_1fr] xl:grid-rows-[1fr_2fr] gap-y-8 p-8 text-sm",
                                ),
                                cls="grid bg-background",
                            ),
                            cls="grid bg-muted p-2",
                        ),
                        id=f"text-column-{idx}",
                        cls="text-column relative bg-background px-3 py-5 hidden md-grid-text-column",
                    ),
                    id=f"image-text-columns-{idx}",
                    cls="relative grid grid-cols-1 border-t grid-image-text-columns",
                ),
                cls="grid grid-cols-1 grid-rows-[auto_auto_1fr]",
            ),
        )

    return [
        Div(
            SearchInfo(search_time, total_count),
            *result_items,
            image_swapping,
            toggle_text_content,
            dynamic_elements_scrollbars,
            id="search-results",
            cls="grid grid-cols-1 gap-px bg-border min-h-0",
        ),
        Div(
            ChatResult(query_id=query_id, query=query, doc_ids=doc_ids),
            hx_swap_oob="true",
            id="chat_messages",
        ),
    ]


def ChatResult(query_id: str, query: str, doc_ids: Optional[list] = None):
    messages = Div(LoadingSkeleton())

    if doc_ids:
        messages = Div(
            LoadingSkeleton(),
            hx_ext="sse",
            sse_connect=f"/get-message?query_id={query_id}&doc_ids={','.join(doc_ids)}&query={quote_plus(query)}",
            sse_swap="message",
            sse_close="close",
            hx_swap="innerHTML",
        )

    return Div(
        Div("AI-response", cls="text-xl font-semibold p-5"),
        Div(
            Div(
                messages,
            ),
            id="chat-messages",
            cls="overflow-auto min-h-0 grid items-end px-5",
        ),
        id="chat_messages",
        cls="h-full grid grid-rows-[auto_1fr_auto] min-h-0 gap-3",
    )


def UploadForm():
    """File upload form component with metadata fields."""
    return Form(
        Div(
            Div(
                Label("PDF File", htmlFor="pdf_file", cls="text-sm font-medium"),
                Div(
                    Lucide(
                        icon="file-up",
                        cls="absolute left-3 top-1/2 -translate-y-1/2 text-muted-foreground",
                    ),
                    Div(
                        "Choose a PDF file (max 250MB)",
                        id="file-label",
                        cls="text-sm text-muted-foreground",
                    ),
                    HtmlInput(
                        type="file",
                        name="pdf_file",
                        id="pdf_file",
                        accept=".pdf,application/pdf",
                        cls="absolute inset-0 w-full h-full opacity-0 cursor-pointer",
                        onchange="document.getElementById('file-label').textContent = this.files[0]?.name || 'Choose a PDF file (max 250MB)'",
                    ),
                    cls="relative flex items-center gap-2 pl-10 pr-4 py-3 border border-input rounded-md bg-background hover:bg-muted cursor-pointer",
                ),
                cls="grid gap-2",
            ),
            Div(
                Label("Title (optional)", htmlFor="title", cls="text-sm font-medium"),
                Input(
                    type="text",
                    name="title",
                    id="title",
                    placeholder="Custom document title",
                    maxlength=str(get("app", "validation", "max_title_length")),
                    cls="border border-input rounded-md px-3 py-2",
                ),
                cls="grid gap-2",
            ),
            Div(
                Label(
                    "Description (optional)",
                    htmlFor="description",
                    cls="text-sm font-medium",
                ),
                Textarea(
                    name="description",
                    id="description",
                    placeholder="Brief description of the document",
                    maxlength=str(get("app", "validation", "max_description_length")),
                    rows="3",
                    cls="border border-input rounded-md px-3 py-2 resize-none w-full",
                ),
                cls="grid gap-2",
            ),
            Div(
                Label("Tags (optional)", htmlFor="tags", cls="text-sm font-medium"),
                Input(
                    type="text",
                    name="tags",
                    id="tags",
                    placeholder="Comma-separated tags (e.g., finance, report, 2024)",
                    cls="border border-input rounded-md px-3 py-2",
                ),
                P(
                    f"Maximum {get('app', 'validation', 'max_tags')} tags, each up to {get('app', 'validation', 'max_tag_length')} characters",
                    cls="text-xs text-muted-foreground",
                ),
                cls="grid gap-2",
            ),
            Button(
                Lucide(icon="upload", cls="mr-2"),
                "Upload PDF",
                type="submit",
                cls="w-full",
            ),
            cls="grid gap-6",
        ),
        hx_post="/upload",
        hx_encoding="multipart/form-data",
        hx_target="#upload-result",
        hx_swap="innerHTML",
        hx_indicator="#upload-indicator",
        cls="grid gap-4 p-6 bg-muted rounded-lg border border-input max-w-lg mx-auto",
    )


def UploadPage():
    """Upload page wrapper component."""
    return Div(
        Div(
            H1("Upload PDF Document", cls="text-3xl font-bold tracking-wide"),
            P(
                "Upload a PDF document to make it searchable. The document will be processed and indexed for visual retrieval.",
                cls="text-muted-foreground",
            ),
            cls="text-center grid gap-2 mb-8",
        ),
        UploadForm(),
        Div(
            Div(
                Lucide(icon="loader-circle", cls="size-5 mr-1.5 animate-spin"),
                Span("Processing your document...", cls="text-base"),
                cls="flex items-center justify-center text-muted-foreground",
            ),
            id="upload-indicator",
            cls="htmx-indicator p-4",
        ),
        Div(id="upload-result", cls="mt-6"),
        cls="w-full max-w-screen-md mx-auto mt-[8vh] px-4",
    )


def UploadSidebar():
    """Sidebar navigation for the upload page."""
    return Div(
        Div(
            H3("Quick Links", cls="text-lg font-semibold mb-4"),
            Div(
                A(
                    Div(
                        Lucide(icon="search", size="18"),
                        Span("Search Documents"),
                        cls="flex items-center gap-2",
                    ),
                    href="/",
                    cls="block p-2 rounded-md hover:bg-muted transition-colors",
                ),
                A(
                    Div(
                        Lucide(icon="info", size="18"),
                        Span("About This Demo"),
                        cls="flex items-center gap-2",
                    ),
                    href="/about-this-demo",
                    cls="block p-2 rounded-md hover:bg-muted transition-colors",
                ),
                cls="grid gap-1",
            ),
            cls="mb-8",
        ),
        Div(
            H3("Upload Tips", cls="text-lg font-semibold mb-4"),
            Ul(
                Li(
                    Div(
                        Lucide(
                            icon="file-check", size="16", cls="text-green-500 mt-0.5"
                        ),
                        Span(
                            "PDF files up to 250MB", cls="text-sm text-muted-foreground"
                        ),
                        cls="flex items-start gap-2",
                    ),
                ),
                Li(
                    Div(
                        Lucide(icon="tag", size="16", cls="text-blue-500 mt-0.5"),
                        Span(
                            "Add tags to improve search relevance",
                            cls="text-sm text-muted-foreground",
                        ),
                        cls="flex items-start gap-2",
                    ),
                ),
                Li(
                    Div(
                        Lucide(icon="clock", size="16", cls="text-orange-500 mt-0.5"),
                        Span(
                            "Large files may take a few minutes to process",
                            cls="text-sm text-muted-foreground",
                        ),
                        cls="flex items-start gap-2",
                    ),
                ),
                Li(
                    Div(
                        Lucide(icon="lock", size="16", cls="text-red-500 mt-0.5"),
                        Span(
                            "Password-protected PDFs are not supported",
                            cls="text-sm text-muted-foreground",
                        ),
                        cls="flex items-start gap-2",
                    ),
                ),
                cls="grid gap-3",
            ),
            cls="mb-8",
        ),
        Div(
            H3("Supported Content", cls="text-lg font-semibold mb-4"),
            P(
                "ColPali uses visual embeddings to understand document content including:",
                cls="text-sm text-muted-foreground mb-3",
            ),
            Ul(
                Li("Text and paragraphs", cls="text-sm text-muted-foreground"),
                Li("Tables and charts", cls="text-sm text-muted-foreground"),
                Li("Images and diagrams", cls="text-sm text-muted-foreground"),
                Li("Infographics", cls="text-sm text-muted-foreground"),
                cls="list-disc list-inside grid gap-1",
            ),
        ),
        cls="p-5",
    )


def UploadSuccess(title: str, pages_indexed: int):
    """Success message component after successful upload."""
    return Div(
        Div(
            Lucide(icon="check-circle", size="48", cls="text-green-500"),
            cls="flex justify-center mb-4",
        ),
        H3("Upload Successful", cls="text-xl font-semibold text-center"),
        P(
            f'Document "{title}" has been processed.',
            cls="text-center text-muted-foreground",
        ),
        P(
            f"{pages_indexed} pages indexed and ready for search.",
            cls="text-center text-muted-foreground",
        ),
        Div(
            A(
                Button(
                    Lucide(icon="search", cls="mr-2"),
                    "Go to Search",
                    variant="default",
                ),
                href="/",
            ),
            A(
                Button(
                    Lucide(icon="upload", cls="mr-2"),
                    "Upload Another",
                    variant="outline",
                ),
                href="/upload",
            ),
            cls="flex justify-center gap-4 mt-6",
        ),
        cls="p-6 bg-green-50 dark:bg-green-950 rounded-lg border border-green-200 dark:border-green-800",
    )


def UploadError(error_message: str):
    """Error message component for upload failures."""
    return Div(
        Div(
            Lucide(icon="x-circle", size="48", cls="text-red-500"),
            cls="flex justify-center mb-4",
        ),
        H3("Upload Failed", cls="text-xl font-semibold text-center"),
        P(
            error_message,
            cls="text-center text-muted-foreground",
        ),
        Div(
            A(
                Button(
                    Lucide(icon="refresh-cw", cls="mr-2"),
                    "Try Again",
                    variant="default",
                ),
                href="/upload",
            ),
            cls="flex justify-center mt-6",
        ),
        cls="p-6 bg-red-50 dark:bg-red-950 rounded-lg border border-red-200 dark:border-red-800",
    )


# =============================================================================
# Visual Document Search Components
# =============================================================================

# JavaScript for managing page selection state
visual_search_selection_script = Script(
    """
    (function() {
        // Selection state management
        window.VisualSearchState = {
            selectedPages: new Map(),  // doc_id -> {title, page_number, relevance, blur_image}

            toggleSelection: function(docId, metadata) {
                if (this.selectedPages.has(docId)) {
                    this.selectedPages.delete(docId);
                } else {
                    this.selectedPages.set(docId, metadata);
                }
                this.updateUI();
            },

            clearSelection: function() {
                this.selectedPages.clear();
                this.updateUI();
            },

            selectTopN: function(n) {
                // Get all result cards in order
                const cards = document.querySelectorAll('[data-result-card]');
                this.clearSelection();
                cards.forEach((card, idx) => {
                    if (idx < n) {
                        const docId = card.dataset.docId;
                        const metadata = JSON.parse(card.dataset.metadata);
                        this.selectedPages.set(docId, metadata);
                    }
                });
                this.updateUI();
            },

            updateUI: function() {
                const count = this.selectedPages.size;

                // Update footer visibility and count
                const footer = document.getElementById('selection-footer');
                const countEl = document.getElementById('selection-count');
                const getAnswerBtn = document.getElementById('get-answer-btn');

                if (footer) {
                    if (count > 0) {
                        footer.classList.remove('translate-y-full', 'opacity-0');
                        footer.classList.add('translate-y-0', 'opacity-100');
                    } else {
                        footer.classList.add('translate-y-full', 'opacity-0');
                        footer.classList.remove('translate-y-0', 'opacity-100');
                    }
                }

                if (countEl) {
                    countEl.textContent = count + (count === 1 ? ' page' : ' pages') + ' selected';
                }

                if (getAnswerBtn) {
                    getAnswerBtn.disabled = count === 0;
                }

                // Update card visual states
                document.querySelectorAll('[data-result-card]').forEach(card => {
                    const docId = card.dataset.docId;
                    const checkbox = card.querySelector('[data-checkbox]');
                    const isSelected = this.selectedPages.has(docId);

                    if (isSelected) {
                        card.classList.add('ring-2', 'ring-primary', 'ring-offset-2');
                        if (checkbox) checkbox.checked = true;
                    } else {
                        card.classList.remove('ring-2', 'ring-primary', 'ring-offset-2');
                        if (checkbox) checkbox.checked = false;
                    }
                });
            },

            getSelectedDocIds: function() {
                return Array.from(this.selectedPages.keys());
            }
        };

        // Event delegation for card selection
        document.addEventListener('click', function(e) {
            // Handle checkbox click
            const checkbox = e.target.closest('[data-checkbox]');
            if (checkbox) {
                e.preventDefault();
                const card = checkbox.closest('[data-result-card]');
                if (card) {
                    const docId = card.dataset.docId;
                    const metadata = JSON.parse(card.dataset.metadata);
                    window.VisualSearchState.toggleSelection(docId, metadata);
                }
                return;
            }

            // Handle thumbnail click (opens modal)
            const thumbnail = e.target.closest('[data-thumbnail]');
            if (thumbnail) {
                const card = thumbnail.closest('[data-result-card]');
                if (card) {
                    const docId = card.dataset.docId;
                    window.openPageDetailModal(docId);
                }
                return;
            }
        });

        // Handle "Select top N" dropdown
        document.addEventListener('change', function(e) {
            if (e.target.id === 'select-top-n') {
                const n = parseInt(e.target.value);
                if (n > 0) {
                    window.VisualSearchState.selectTopN(n);
                }
                e.target.value = '';  // Reset dropdown
            }
        });
    })();
    """
)

# JavaScript for page detail modal
page_detail_modal_script = Script(
    """
    (function() {
        window.openPageDetailModal = function(docId) {
            const modal = document.getElementById('page-detail-modal');
            const content = document.getElementById('modal-content');

            if (modal && content) {
                // Show loading state
                content.innerHTML = '<div class="flex items-center justify-center p-10"><div class="animate-spin rounded-full h-8 w-8 border-b-2 border-primary"></div></div>';
                modal.classList.remove('hidden');
                modal.classList.add('flex');

                // Fetch full page details via HTMX
                htmx.ajax('GET', '/visual-search/page-detail?doc_id=' + docId, {target: '#modal-content', swap: 'innerHTML'});
            }
        };

        window.closePageDetailModal = function() {
            const modal = document.getElementById('page-detail-modal');
            if (modal) {
                modal.classList.add('hidden');
                modal.classList.remove('flex');
            }
        };

        // Close modal on backdrop click
        document.addEventListener('click', function(e) {
            if (e.target.id === 'page-detail-modal') {
                window.closePageDetailModal();
            }
        });

        // Close modal on Escape key
        document.addEventListener('keydown', function(e) {
            if (e.key === 'Escape') {
                window.closePageDetailModal();
            }
        });

        // Navigate between results in modal
        window.navigateModal = function(direction) {
            const cards = document.querySelectorAll('[data-result-card]');
            const currentDocId = document.getElementById('modal-content')?.dataset?.currentDocId;

            if (!currentDocId || !cards.length) return;

            let currentIdx = -1;
            cards.forEach((card, idx) => {
                if (card.dataset.docId === currentDocId) currentIdx = idx;
            });

            let newIdx = currentIdx + direction;
            if (newIdx < 0) newIdx = cards.length - 1;
            if (newIdx >= cards.length) newIdx = 0;

            const newDocId = cards[newIdx].dataset.docId;
            window.openPageDetailModal(newDocId);
        };
    })();
    """
)

# JavaScript for answer synthesis
answer_synthesis_script = Script(
    """
    (function() {
        window.requestAnswerSynthesis = function() {
            const selectedDocIds = window.VisualSearchState.getSelectedDocIds();
            if (selectedDocIds.length === 0) return;

            const queryInput = document.getElementById('visual-search-input');
            const query = queryInput ? queryInput.value : '';

            // Show answer panel
            const answerPanel = document.getElementById('answer-panel');
            const answerContent = document.getElementById('answer-content');

            if (answerPanel && answerContent) {
                answerPanel.classList.remove('hidden');
                answerContent.innerHTML = '<div class="flex items-center gap-2 text-muted-foreground"><div class="animate-spin rounded-full h-4 w-4 border-b-2 border-primary"></div><span>Analyzing ' + selectedDocIds.length + ' pages...</span></div>';

                // Scroll to answer panel
                answerPanel.scrollIntoView({ behavior: 'smooth', block: 'start' });
            }

            // Use SSE to stream the response
            const url = '/visual-search/synthesize?query=' + encodeURIComponent(query) + '&doc_ids=' + selectedDocIds.join(',');
            const eventSource = new EventSource(url);

            eventSource.addEventListener('message', function(e) {
                if (answerContent) {
                    answerContent.innerHTML = e.data;
                }
            });

            eventSource.addEventListener('close', function(e) {
                eventSource.close();
            });

            eventSource.onerror = function(e) {
                eventSource.close();
                if (answerContent && !answerContent.innerHTML.includes('Error')) {
                    answerContent.innerHTML += '<p class="text-red-500 mt-2">Connection closed.</p>';
                }
            };
        };

        window.closeAnswerPanel = function() {
            const answerPanel = document.getElementById('answer-panel');
            if (answerPanel) {
                answerPanel.classList.add('hidden');
            }
        };

        window.refineAnswer = function() {
            // Keep selections but close answer panel for adjustments
            window.closeAnswerPanel();
        };
    })();
    """
)


def VisualSearchBox(query_value=""):
    """Single-line search input for visual document search."""
    return Form(
        Div(
            Lucide(
                icon="search",
                cls="absolute left-3 top-1/2 -translate-y-1/2 text-muted-foreground z-10",
            ),
            Input(
                placeholder="Ask a question about your documents...",
                name="query",
                value=query_value,
                id="visual-search-input",
                cls="text-base pl-10 pr-4 h-12 border border-input rounded-lg bg-background focus-visible:ring-2 focus-visible:ring-primary",
                style="font-size: 1rem",
                autofocus=True,
            ),
            Button(
                Lucide(icon="arrow-right", size="20"),
                type="submit",
                size="icon",
                cls="absolute right-2 top-1/2 -translate-y-1/2",
            ),
            cls="relative w-full max-w-2xl mx-auto",
        ),
        action="/visual-search",
        method="GET",
        cls="w-full",
    )


def VisualSearchResultCard(result: dict, idx: int):
    """Individual result card with selectable thumbnail."""
    fields = result.get("fields", {})
    doc_id = fields.get("id", "")
    title = fields.get("title", "Unknown")
    page_number = fields.get("page_number", 0) + 1
    relevance = result.get("relevance", 0)
    blur_image = fields.get("blur_image", "")

    # Metadata for JavaScript
    metadata = {
        "title": title,
        "page_number": page_number,
        "relevance": relevance,
    }

    relevance_pct = f"{relevance * 100:.0f}%" if relevance <= 1 else f"{relevance:.1f}"

    return Div(
        # Checkbox overlay
        Div(
            HtmlInput(
                type="checkbox",
                data_checkbox="true",
                cls="h-5 w-5 rounded border-2 border-white bg-white/80 cursor-pointer accent-primary",
            ),
            cls="absolute top-2 left-2 z-10 opacity-0 group-hover:opacity-100 transition-opacity",
        ),
        # Relevance badge
        Div(
            Badge(relevance_pct, variant="secondary", cls="text-xs font-mono"),
            cls="absolute top-2 right-2 z-10",
        ),
        # Thumbnail
        Div(
            Img(
                src=f"data:image/jpeg;base64,{blur_image}" if blur_image else "",
                alt=f"{title} - Page {page_number}",
                data_thumbnail="true",
                cls="w-full h-full object-cover cursor-pointer hover:opacity-90 transition-opacity",
            ),
            cls="aspect-[3/4] bg-muted overflow-hidden rounded-t-lg",
        ),
        # Info footer
        Div(
            P(title, cls="text-sm font-medium truncate"),
            P(f"Page {page_number}", cls="text-xs text-muted-foreground"),
            cls="p-2 bg-background border-t",
        ),
        data_result_card="true",
        data_doc_id=doc_id,
        data_metadata=json.dumps(metadata),
        cls="group relative rounded-lg border bg-card overflow-hidden transition-all hover:shadow-md cursor-pointer",
    )


def VisualSearchResultGrid(
    results: list, query: str, query_id: str, search_time: float, total_count: int
):
    """Grid of selectable result thumbnails."""
    if not results:
        return Div(
            Div(
                Lucide(icon="search-x", size="48", cls="text-muted-foreground mb-4"),
                P("No matching pages found.", cls="text-lg font-medium"),
                P("Try a different query.", cls="text-muted-foreground"),
                cls="flex flex-col items-center justify-center py-16",
            ),
            id="visual-search-results",
        )

    result_cards = [
        VisualSearchResultCard(result, idx) for idx, result in enumerate(results)
    ]

    return Div(
        # Search info
        Div(
            Span(
                f"Found {total_count} results in {search_time:.2f}s",
                cls="text-sm text-muted-foreground",
            ),
            Div(
                Label(
                    "Select:",
                    htmlFor="select-top-n",
                    cls="text-sm text-muted-foreground",
                ),
                Div(
                    HtmlInput(
                        type="button",
                        value="Top 3",
                        onclick="window.VisualSearchState.selectTopN(3)",
                        cls="px-2 py-1 text-xs border rounded hover:bg-muted cursor-pointer",
                    ),
                    HtmlInput(
                        type="button",
                        value="Top 5",
                        onclick="window.VisualSearchState.selectTopN(5)",
                        cls="px-2 py-1 text-xs border rounded hover:bg-muted cursor-pointer",
                    ),
                    HtmlInput(
                        type="button",
                        value="Top 10",
                        onclick="window.VisualSearchState.selectTopN(10)",
                        cls="px-2 py-1 text-xs border rounded hover:bg-muted cursor-pointer",
                    ),
                    cls="flex gap-1",
                ),
                cls="flex items-center gap-2",
            ),
            cls="flex items-center justify-between px-4 py-3 bg-muted/50 border-b",
        ),
        # Results grid
        Div(
            *result_cards,
            cls="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 lg:grid-cols-5 gap-4 p-4",
        ),
        id="visual-search-results",
        cls="min-h-0 overflow-auto",
    )


def SelectionFooter():
    """Sticky footer showing selection count and Get Answer button."""
    return Div(
        Div(
            Div(
                Span(
                    "0 pages selected", id="selection-count", cls="text-sm font-medium"
                ),
                Button(
                    "Clear",
                    variant="link",
                    size="sm",
                    onclick="window.VisualSearchState.clearSelection()",
                    cls="text-muted-foreground",
                ),
                cls="flex items-center gap-4",
            ),
            Button(
                Lucide(icon="sparkles", cls="mr-2"),
                "Get Answer from Selection",
                id="get-answer-btn",
                onclick="window.requestAnswerSynthesis()",
                disabled=True,
                cls="",
            ),
            cls="flex items-center justify-between max-w-4xl mx-auto w-full",
        ),
        id="selection-footer",
        cls="fixed bottom-0 left-0 right-0 bg-background border-t shadow-lg px-4 py-3 transition-all duration-300 translate-y-full opacity-0 z-50",
    )


def AnswerPanel():
    """Panel displaying the synthesized answer."""
    return Div(
        Div(
            Div(
                H2("Answer", cls="text-lg font-semibold"),
                Div(
                    Button(
                        "Refine",
                        variant="outline",
                        size="sm",
                        onclick="window.refineAnswer()",
                    ),
                    Button(
                        Lucide(icon="x", size="16"),
                        variant="ghost",
                        size="icon",
                        onclick="window.closeAnswerPanel()",
                    ),
                    cls="flex items-center gap-2",
                ),
                cls="flex items-center justify-between mb-4",
            ),
            Div(
                id="answer-content",
                cls="prose prose-sm dark:prose-invert max-w-none",
            ),
            cls="p-6 bg-card border rounded-lg shadow-sm max-w-4xl mx-auto",
        ),
        id="answer-panel",
        cls="hidden px-4 py-6 bg-muted/30 border-b",
    )


def PageDetailModal():
    """Modal for viewing full page details."""
    return Div(
        Div(
            # Close button
            Button(
                Lucide(icon="x", size="20"),
                variant="ghost",
                size="icon",
                onclick="window.closePageDetailModal()",
                cls="absolute top-4 right-4 z-10",
            ),
            # Navigation arrows
            Button(
                Lucide(icon="chevron-left", size="24"),
                variant="ghost",
                size="icon",
                onclick="window.navigateModal(-1)",
                cls="absolute left-4 top-1/2 -translate-y-1/2 z-10",
            ),
            Button(
                Lucide(icon="chevron-right", size="24"),
                variant="ghost",
                size="icon",
                onclick="window.navigateModal(1)",
                cls="absolute right-4 top-1/2 -translate-y-1/2 z-10",
            ),
            # Content container
            Div(
                id="modal-content",
                cls="bg-background rounded-lg shadow-xl max-w-4xl max-h-[90vh] overflow-auto",
            ),
            cls="relative w-full h-full flex items-center justify-center p-4",
        ),
        id="page-detail-modal",
        cls="hidden fixed inset-0 bg-black/50 z-50 items-center justify-center",
    )


def PageDetailContent(doc_id: str, fields: dict, is_selected: bool = False):
    """Content for the page detail modal."""
    title = fields.get("title", "Unknown")
    page_number = fields.get("page_number", 0) + 1
    text = fields.get("text", "")
    url = fields.get("url", "")
    blur_image = fields.get("blur_image", "")

    return Div(
        # Header
        Div(
            Div(
                H2(title, cls="text-xl font-semibold"),
                Badge(f"Page {page_number}", variant="outline"),
                cls="flex items-center gap-2",
            ),
            cls="p-4 border-b",
        ),
        # Image
        Div(
            Img(
                src=f"data:image/jpeg;base64,{blur_image}" if blur_image else "",
                hx_get=f"/full_image?doc_id={doc_id}",
                hx_trigger="load",
                hx_swap="outerHTML",
                alt=f"{title} - Page {page_number}",
                cls="max-h-[50vh] w-auto mx-auto",
            ),
            cls="p-4 bg-muted",
        ),
        # Actions
        Div(
            Button(
                Lucide(icon="check" if is_selected else "plus", cls="mr-2"),
                "Selected" if is_selected else "Select this page",
                variant="default" if is_selected else "outline",
                onclick=f"window.VisualSearchState.toggleSelection('{doc_id}', {json.dumps({'title': title, 'page_number': page_number})}); window.closePageDetailModal();",
            ),
            A(
                Button(
                    Lucide(icon="external-link", cls="mr-2"),
                    "View PDF",
                    variant="outline",
                ),
                href=f"{url}#page={page_number}" if url else "#",
                target="_blank",
            ),
            cls="flex items-center gap-2 p-4 border-t",
        ),
        # Text preview
        Div(
            H3("Page Text", cls="text-sm font-semibold mb-2"),
            P(
                text[:1000] + "..." if len(text) > 1000 else text,
                cls="text-sm text-muted-foreground whitespace-pre-wrap",
            ),
            cls="p-4 border-t max-h-48 overflow-auto",
        )
        if text
        else None,
        data_current_doc_id=doc_id,
        cls="bg-background",
    )


def VisualSearchPage(query: str = ""):
    """Main visual search page component."""
    return Div(
        # Answer panel (hidden initially)
        AnswerPanel(),
        # Main content
        Div(
            # Search bar
            Div(
                VisualSearchBox(query_value=query),
                cls="px-4 py-6 border-b bg-background sticky top-0 z-40",
            ),
            # Results area (loaded via HTMX)
            Div(
                LoadingMessage("Searching documents...")
                if query
                else Div(
                    Div(
                        Lucide(
                            icon="file-search",
                            size="48",
                            cls="text-muted-foreground mb-4",
                        ),
                        P(
                            "Enter a question to search your documents",
                            cls="text-lg font-medium text-muted-foreground",
                        ),
                        cls="flex flex-col items-center justify-center py-16",
                    ),
                ),
                id="visual-search-results",
                hx_get=f"/visual-search/results?query={quote_plus(query)}"
                if query
                else None,
                hx_trigger="load" if query else None,
                hx_swap="outerHTML",
            ),
            cls="flex-1 min-h-0 overflow-auto",
        ),
        # Selection footer
        SelectionFooter(),
        # Page detail modal
        PageDetailModal(),
        # Scripts
        visual_search_selection_script,
        page_detail_modal_script,
        answer_synthesis_script,
        cls="flex flex-col h-full",
    )

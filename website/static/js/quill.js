// TO DO 
// The current code adds <p><br></p> between any paragraph, if not originally entered
// in Quill. Very annoying. Ideally someone more js-versed can fixed it; I can't. 
// Reproduce by having <p>hello</p><p>hello</p> in the db and this gets loaded
// by Quill with the extra <p><br></p> in-between the paragraphs.

(function() {
  const Delta = Quill.import('delta');
  const BlockEmbed = Quill.import('blots/block/embed');
  const Parchment = Quill.import('parchment');

  // Generic HTML blot for ANY unknown tag (divs, sections, etc.)
  class GenericHtmlBlot extends BlockEmbed {
    static blotName = 'html-raw';
    static tagName = 'DIV';
    static className = 'ql-html-raw';

    static create(value) {
      if (typeof value === 'string') {
        const temp = document.createElement('div');
        temp.innerHTML = value;
        return temp.firstElementChild || super.create();
      }
      const node = super.create();
      if (value.tagName) node.tagName = value.tagName;
      if (value.attrs) {
        Object.entries(value.attrs).forEach(([key, val]) => {
          if (val !== null && val !== undefined) node.setAttribute(key, val);
        });
      }
      if (value.innerHTML) node.innerHTML = value.innerHTML;
      return node;
    }

    static value(node) {
      return {
        tagName: node.tagName,
        attrs: Array.from(node.attributes).reduce((acc, attr) => {
          acc[attr.name] = attr.value;
          return acc;
        }, {}),
        innerHTML: node.innerHTML
      };
    }
  }
  Quill.register(GenericHtmlBlot);

  // Video blot (your original, preserved)
  class HtmlVideoBlot extends BlockEmbed {
    static blotName = 'html-video';
    static tagName = 'video';
    static className = 'ql-html-video';

    static create(value) {
      const node = super.create();
      const v = (typeof value === 'string') ? { src: value } : (value || {});

      if (v.src) {
        const source = document.createElement('source');
        source.setAttribute('src', v.src);
        if (v.type) source.setAttribute('type', v.type);
        node.appendChild(source);
      } else if (v.sources && Array.isArray(v.sources)) {
        v.sources.forEach(s => {
          if (!s || !s.src) return;
          const source = document.createElement('source');
          source.setAttribute('src', s.src);
          if (s.type) source.setAttribute('type', s.type);
          node.appendChild(source);
        });
      }

      if (v.controls) node.setAttribute('controls', '');
      if (v.muted) node.setAttribute('muted', '');
      if (v.loop) node.setAttribute('loop', '');
      if (v.preload) node.setAttribute('preload', v.preload);
      if (v.poster) node.setAttribute('poster', v.poster);
      if (v.width) node.setAttribute('width', v.width);
      if (v.height) node.setAttribute('height', v.height);
      if (v.crossorigin) node.setAttribute('crossorigin', v.crossorigin);

      return node;
    }

    static value(node) {
      const sources = [];
      node.querySelectorAll('source').forEach(s => {
        sources.push({
          src: s.getAttribute('src'),
          type: s.getAttribute('type')
        });
      });
      if (!sources.length && node.getAttribute('src')) {
        sources.push({ src: node.getAttribute('src'), type: node.getAttribute('type') });
      }

      return {
        sources: sources.length ? sources : undefined,
        controls: node.hasAttribute('controls'),
        muted: node.hasAttribute('muted'),
        loop: node.hasAttribute('loop'),
        preload: node.getAttribute('preload'),
        poster: node.getAttribute('poster'),
        width: node.getAttribute('width'),
        height: node.getAttribute('height'),
        crossorigin: node.getAttribute('crossorigin')
      };
    }
  }
  Quill.register(HtmlVideoBlot);

  // Clean clipboard setup - prevents <p><br></p> insertion
  function setupCleanClipboard(quill) {
    // Clear all default matchers to prevent visual spacing insertion
    quill.clipboard.matchers = [];
    
    // Add ONLY custom matcher for videos and raw HTML
    quill.clipboard.addMatcher(Node.ELEMENT_NODE, (node, delta) => {
      // Handle video specifically first
      if (node.tagName === 'VIDEO') {
        const sources = [];
        node.querySelectorAll('source').forEach(s => {
          sources.push({ src: s.getAttribute('src'), type: s.getAttribute('type') });
        });
        if (!sources.length && node.getAttribute('src')) {
          sources.push({ src: node.getAttribute('src'), type: node.getAttribute('type') });
        }
        const value = {
          sources: sources,
          controls: node.hasAttribute('controls'),
          muted: node.hasAttribute('muted'),
          loop: node.hasAttribute('loop'),
          preload: node.getAttribute('preload'),
          poster: node.getAttribute('poster'),
          width: node.getAttribute('width'),
          height: node.getAttribute('height'),
          crossorigin: node.getAttribute('crossorigin')
        };
        return new Delta().insert({ 'html-video': value }).insert('\n');
      }

      // Preserve everything else as raw HTML - NO extra spacing
      const temp = document.createElement('div');
      temp.appendChild(node.cloneNode(true));
      const outerHTML = temp.firstElementChild.outerHTML;
      return new Delta().insert({ 'html-raw': outerHTML }).insert('\n');
    });
    
    // Ensure matchVisual is disabled
    quill.clipboard.options.matchVisual = false;
  }

  $(function() {
    $("textarea.quill").each(function() {
      const textarea = $(this);
      const textareaName = textarea.attr("name");
      const editorContainer = $("#" + textareaName + "-container");

      const quill = new Quill(editorContainer[0], {
        theme: "snow",
        modules: {
          toolbar: [
            [{ header: "1" }, { header: "2" }, { font: [] }],
            [{ list: "ordered" }, { list: "bullet" }],
            ["bold", "italic", "underline"],
            [{ align: [] }],
            ["link", "image"]
          ],
          clipboard: {
            matchVisual: false
          }
        }
      });

      // Setup clean clipboard BEFORE any content loading
      setupCleanClipboard(quill);

      // Preload the HTML content - now without <p><br></p> injection
      const textareaContent = textarea.val() || '';
      if (textareaContent) {
        quill.clipboard.dangerouslyPasteHTML(textareaContent);
      }

      // Sync Quill content to textarea on changes (full HTML preserved)
      quill.on("text-change", function() {
        textarea.val(quill.root.innerHTML);
      });

      // Initial sync
      textarea.val(quill.root.innerHTML);

      textarea.hide();
    });

    $(".show-code").click(function() {
      $("textarea.quill").toggle();
    });
  });
})();

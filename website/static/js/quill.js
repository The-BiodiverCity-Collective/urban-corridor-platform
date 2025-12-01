(function() {
  const Delta = Quill.import('delta');
  const BlockEmbed = Quill.import('blots/block/embed');

  class HtmlVideoBlot extends BlockEmbed {
    static blotName = 'html-video';
    static tagName = 'video';
    static className = 'ql-html-video';

    static create(value) {
      const node = super.create();
      const v = (typeof value === 'string') ? { src: value } : (value || {});

      // Create <source> children from v.src or v.sources
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

      // Boolean attributes
      if (v.controls) node.setAttribute('controls', '');
      if (v.muted) node.setAttribute('muted', '');
      if (v.loop) node.setAttribute('loop', '');

      // Other attributes
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

      // Fallback: if no <source> children, maybe video has src attribute
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

  function addVideoMatcher(quill) {
    quill.clipboard.addMatcher('VIDEO', function(node, delta) {
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
    });
  }

  // Integration with textarea.quill -> #<name>-container
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
          ]
        }
      });

      // Register matcher for this instance
      addVideoMatcher(quill);

      // If textarea has initial HTML, paste it through the clipboard so matcher runs
      const textareaContent = textarea.val() || '';
      if (textareaContent) {
        quill.clipboard.dangerouslyPasteHTML(textareaContent);
      }

      // Sync Quill content to textarea on changes
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

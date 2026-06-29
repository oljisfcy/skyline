const assert = require('assert');
const fs = require('fs');
const path = require('path');

const htmlPath = path.join(__dirname, '..', 'custome_text.html');
const html = fs.readFileSync(htmlPath, 'utf8');

assert(
  html.includes('showLoginMode'),
  'edit mode should show a login form when there is no active session'
);

assert(
  html.includes('signInWithPassword'),
  'login form should authenticate with Supabase email/password auth'
);

assert(
  html.includes('getSession'),
  'edit mode should check the current Supabase session before showing the editor'
);

assert(
  html.includes("showEditMode()"),
  'successful login should continue into edit mode'
);

assert(
  html.includes('.update({ content: newText })'),
  'saving should still update only the content field'
);

assert(
  html.includes("get('format')"),
  'init should read a format query parameter'
);

assert(
  html.includes("format === 'raw'"),
  'raw format should have a dedicated branch before normal view/edit modes'
);

assert(
  html.includes('showRawText'),
  'raw format should render only the saved text'
);

assert(
  html.includes('document.body.textContent = data.content ||'),
  'raw format should write the content as textContent'
);

assert(
  html.includes('copyRawLink'),
  'view mode should provide a button for copying the raw text link'
);

assert(
  html.includes("url.searchParams.set('format', 'raw')"),
  'copy raw link should add format=raw to the current page URL'
);

console.log('custome_text auth and raw checks passed');

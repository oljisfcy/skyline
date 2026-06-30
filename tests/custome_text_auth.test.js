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
  'view mode should provide a button for copying the Supabase API link'
);

assert(
  html.includes('goEditMode'),
  'view mode should use a button to enter edit mode'
);

assert(
  html.includes('getSupabaseContentUrl'),
  'copy button should build a Supabase REST content URL'
);

assert(
  html.includes('/rest/v1/'),
  'Supabase content URL should use the REST endpoint'
);

assert(
  html.includes('?select=content&id=eq.'),
  'Supabase content URL should select only the content field for the configured row'
);

assert(
  html.includes('getApiShortcutText'),
  'copy button should copy URL plus Shortcut headers'
);

assert(
  html.includes('apikey: ${SUPABASE_ANON_KEY}'),
  'Shortcut copy text should include the apikey header'
);

assert(
  html.includes('Authorization: Bearer ${SUPABASE_ANON_KEY}'),
  'Shortcut copy text should include the Authorization header'
);

assert(
  html.includes('Accept: application/json'),
  'Shortcut copy text should include the Accept header'
);

assert(
  html.includes('@media (max-width: 600px)'),
  'page should include mobile-friendly styles'
);

assert(
  html.includes('name="viewport"'),
  'page should include a viewport meta tag for mobile rendering'
);

assert(
  html.includes('width=device-width, initial-scale=1'),
  'viewport should render at the device width without desktop scaling'
);

assert(
  html.includes('.toolbar { display: grid; grid-template-columns: 1fr;'),
  'main action buttons should be vertically stacked'
);

console.log('custome_text auth and raw checks passed');

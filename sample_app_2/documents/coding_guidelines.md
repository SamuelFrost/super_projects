# Coding guidelines

## Generate Rails files

Prefer `bin/rails generate` for new application code. Run the generator inside the app container, then adjust the generated files and tests until the feature works.

## Use ERB through ReActionView and Herb

Render pages with ERB templates under `app/views`. ReActionView compiles those templates with Herb (`config.intercept_erb`) and provides reactive templates (`config.slots`). This app uses Hotwire (Turbo and Stimulus) with import maps for the small amount of browser behavior that does not belong in the template.

Do not add React, Vue, or another client-side application framework. Do not introduce a separate frontend build, package, or API whose only job is to serve a JavaScript UI.

# Tool interaction guideline — attach images and videos with GitHub CLI

When adding images or videos to issues, pull requests, or comments, use `gh --attach <path>` rather than committing the media or referencing local paths. If the Markdown body references the local path (e.g. `![alt](path/to/image.png)`), GitHub CLI uploads the file and rewrites the reference to the hosted asset URL. Files not referenced in the body are appended automatically.

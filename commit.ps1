# THIS FILE IS A PART OF FORGEBUILD
# FORGEBUILD IS LICENSED UNDER THE MIT LICENSE.
# SEE MORE DETAILS AT https://opensource.org/licenses/MIT
# OR THE LICENSE FILE IN THE ROOT DIRECTORY OF THIS PROJECT.
# OR THE GITHUB REPOSITORY AT https://github.com/glkdrlgkrlzflnjkgh/ForgeBuild
param(
    [string]$Message = "Utility commit",
    [bool]$Push = $false
)

# Stage all tracked changes and commit with Signed-off-by
git commit -s -a -m $Message

if ($Push) {
    git push
}
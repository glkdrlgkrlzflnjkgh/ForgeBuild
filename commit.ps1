param(
    [string]$Message = "Utility commit"
)

# Stage all tracked changes and commit with Signed-off-by
git commit -s -a -m $Message
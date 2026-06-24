@echo off
echo Deploying OpenMycoNet...
git add -A
git commit -m "update %date% %time%"
git push
echo Done! 
pause
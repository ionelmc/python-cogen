@echo off
set /a count=0
set /a fails=0
:do
echo runs: %count% fails: %fails% command: %*
%*
set /a count=%count%+1
if %errorlevel%==0 goto do
set /a fails=%fails%+1
goto do

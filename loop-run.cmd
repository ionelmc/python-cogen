@echo off
set /a count=0
set /a fails=0
:do
set /a count=%count%+1
echo runs: %count% fails: %fails% command: %*
%*
if %errorlevel%==0 goto do
set /a fails=%fails%+1
goto do

FROM texlive/texlive:latest

RUN tlmgr update --self && \
    tlmgr install \
    enumitem \
    titlesec \
    xcharter \
    xcharter-math \
    fontaxes \
    etoolbox \
    xstring \
    geometry \
    fancyhdr \
    xkeyval \
    microtype \
    hyperxmp \
    datetime2 \
    datetime2-english \
    embedfile

WORKDIR /data
ENTRYPOINT ["pdflatex"]

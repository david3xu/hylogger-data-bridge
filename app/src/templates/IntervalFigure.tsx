// Render the synthetic depth-interval overlap geometry figure.
export function IntervalFigure() {
  return (
    <figure className="interval-figure">
      <svg viewBox="0 0 600 150" role="img" aria-labelledby="interval-title interval-description">
        <title id="interval-title">Synthetic depth interval overlap</title>
        <desc id="interval-description">
          A synthetic candidate extends from 214 to 220 metres. A synthetic assay record covers 215
          to 218 metres. They overlap for 3 metres.
        </desc>
        <g className="figure-grid">
          <line x1="120" y1="28" x2="120" y2="113" />
          <line x1="190" y1="28" x2="190" y2="113" />
          <line x1="400" y1="28" x2="400" y2="113" />
          <line x1="540" y1="28" x2="540" y2="113" />
        </g>
        <text x="0" y="58">
          Candidate
        </text>
        <text x="0" y="99">
          Assay record
        </text>
        <rect x="120" y="39" width="420" height="26" rx="3" className="candidate-bar" />
        <rect x="190" y="80" width="210" height="26" rx="3" className="assay-bar" />
        <g className="depth-labels">
          <text x="120" y="137">
            214 m
          </text>
          <text x="190" y="137">
            215
          </text>
          <text x="400" y="137">
            218
          </text>
          <text x="540" y="137">
            220 m
          </text>
        </g>
      </svg>
      <figcaption>
        Illustrative geometry · 3 m overlap / 6 m candidate = 50%. All values are synthetic.
      </figcaption>
    </figure>
  );
}

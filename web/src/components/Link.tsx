import type { AnchorHTMLAttributes, MouseEvent } from 'react'

import { navigate } from '../lib/router'

export function Link({ href = '/', onClick, ...rest }: AnchorHTMLAttributes<HTMLAnchorElement>) {
  const handle = (event: MouseEvent<HTMLAnchorElement>) => {
    onClick?.(event)
    if (
      event.defaultPrevented ||
      event.button !== 0 ||
      event.metaKey ||
      event.ctrlKey ||
      event.shiftKey
    )
      return
    event.preventDefault()
    navigate(href)
  }
  return <a href={href} onClick={handle} {...rest} />
}
